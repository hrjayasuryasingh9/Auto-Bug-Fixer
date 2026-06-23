"""Autonomous issue → PR agent.

Given a GitHub issue, this:
  1. reads the issue (title, description, screenshots, labels)
  2. clones the repo
  3. gathers the most relevant source files (graph + code search)
  4. asks Claude (with vision for screenshots) to plan minimal multi-file changes
  5. writes the changes, commits to a branch, pushes, and opens a draft PR
"""
from __future__ import annotations

import base64
import json
import os
import re
import time

from server.adapters.github_adapter import (
    get_issue_detail, get_repo_tree_summary, search_code_in_repo, fetch_image_bytes,
)
from server.services.clone_repo import clone_repo
from server.services.graph_service import graph_exists, relevant_files, build_graph
from server.services.create_pr import open_pr, NoChangesError
from server.utils.ai import get_client
from server.utils.shell import run_cmd
from server.utils.credentials import github_token, anthropic_key
from server.utils.logger import logger

_FENCE_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)
_MAX_FILES_CONTEXT = 10
_MAX_FILE_CHARS = 9000

# Claude Sonnet 4.6 pricing (USD per token)
_SONNET_IN_PRICE = 3.0 / 1_000_000
_SONNET_OUT_PRICE = 15.0 / 1_000_000
_USD_TO_INR = 84.0

_SYSTEM = """You are a senior software engineer who resolves GitHub issues by editing a repository.

You are given: the issue (title, description, screenshots), the repo's file tree, and the full text of the most relevant source files. Produce the MINIMAL set of file changes that resolves the issue.

Rules:
- Only change what's necessary; do not refactor unrelated code or reformat.
- Preserve existing behavior and imports; keep the project's style.
- For every file you change, output its COMPLETE new content (not a diff).
- You may create new files if genuinely needed.
- If the context is insufficient to fix it safely, still make your best, smallest reasonable change.

Output format — EXACTLY this plain text, NOT JSON, no markdown fences, no escaping:

SUMMARY: <one to three sentences on what you changed and why>

Then, for each file you change or create, a block:
<<<FILE relative/path/to/file>>>
<the complete new file content, verbatim>
<<<END>>>

Output nothing else before or after these blocks."""


def _safe_join(repo_path: str, rel: str) -> str | None:
    """Join rel under repo_path, rejecting traversal/absolute paths."""
    rel = (rel or "").lstrip("/").replace("\\", "/")
    full = os.path.normpath(os.path.join(repo_path, rel))
    root = os.path.abspath(repo_path)
    if os.path.abspath(full).startswith(root + os.sep) or os.path.abspath(full) == root:
        return full
    return None


def _read_clone_file(repo_path: str, rel: str, max_chars: int = _MAX_FILE_CHARS) -> str | None:
    full = _safe_join(repo_path, rel)
    if full and os.path.isfile(full):
        try:
            with open(full, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()[:max_chars]
        except Exception:
            return None
    return None


async def _pick_files(owner: str, repo: str, issue: dict, token: str) -> list[str]:
    text = f"{issue['title']} {issue.get('body_full') or issue.get('body','')}"
    files: list[str] = []
    if graph_exists(owner, repo):
        for p in relevant_files(owner, repo, text, limit=8):
            if p not in files:
                files.append(p)
    terms = [w for w in re.findall(r"[A-Za-z0-9_]+", text) if len(w) > 3][:6]
    if terms:
        for p in await search_code_in_repo(owner, repo, " ".join(terms[:5]), token, max_results=8):
            if p not in files:
                files.append(p)
    return files[:_MAX_FILES_CONTEXT]


async def _image_blocks(issue: dict, token: str, limit: int = 3) -> list[dict]:
    blocks = []
    for url in (issue.get("images") or [])[:limit]:
        got = await fetch_image_bytes(url, token)
        if got:
            data, mime = got
            blocks.append({
                "type": "image",
                "source": {"type": "base64", "media_type": mime, "data": base64.b64encode(data).decode()},
            })
    return blocks


_FILE_RE = re.compile(r"<<<FILE\s+(.+?)>>>[ \t]*\n(.*?)\n[ \t]*<<<END>>>", re.DOTALL)


def _parse_changes(raw: str) -> dict:
    """Parse the delimiter format (robust for code). Falls back to JSON if present."""
    summary_m = re.search(r"SUMMARY:\s*(.+)", raw)
    summary = summary_m.group(1).strip() if summary_m else "AI-generated fix."

    changes = []
    for m in _FILE_RE.finditer(raw):
        path = m.group(1).strip().strip("`\"' ")
        content = m.group(2)
        if path:
            changes.append({"path": path, "content": content})

    if changes:
        return {"summary": summary, "changes": changes}

    # Fallback: maybe the model returned JSON after all.
    fence = _FENCE_RE.search(raw)
    data = json.loads((fence.group(1) if fence else raw).strip())
    return {"summary": data.get("summary", summary), "changes": data.get("changes", [])}


async def _emit(progress, stage: str, message: str) -> None:
    """Push a real progress event to the caller (drives the live Slack loader)."""
    logger.info(f"[fix_issue] {stage}: {message}")
    if progress:
        try:
            await progress({"stage": stage, "message": message})
        except Exception:
            pass


async def fix_issue(owner: str, repo: str, issue_number: int, progress=None) -> dict:
    token = github_token()
    key = anthropic_key()
    if not token:
        return {"success": False, "error": "No GITHUB_TOKEN configured on the server."}
    if not key:
        return {"success": False, "error": "No ANTHROPIC_API_KEY configured on the server."}

    logger.info(f"[fix_issue] === issue #{issue_number} in {owner}/{repo} ===")

    # 1) Issue
    await _emit(progress, "issue", f"Reading issue #{issue_number}")
    issue = await get_issue_detail(owner, repo, issue_number, token)

    # 2) Clone
    await _emit(progress, "clone", "Cloning the repository")
    repo_url = f"https://github.com/{owner}/{repo}.git"
    repo_path = await clone_repo(repo_url, repo, token)
    base_branch = (await run_cmd(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_path)).strip() or "main"

    # 2b) Build/refresh the knowledge graph from THIS clone, then use it below.
    await _emit(progress, "graph", "Building the knowledge graph")
    try:
        g = await build_graph(owner, repo, token, repo_path=repo_path)
        logger.info(f"[fix_issue] graph: status={g.get('status')} nodes={g.get('nodes')}")
        if g.get("status") == "ok":
            await _emit(progress, "graph", f"Built knowledge graph — {g.get('nodes')} nodes, {g.get('communities')} areas")
    except Exception as e:
        logger.warning(f"[fix_issue] graph build failed (continuing with code search): {e}")

    # 3) Relevant source
    await _emit(progress, "analyze", "Selecting the most relevant files")
    paths = await _pick_files(owner, repo, issue, token)
    file_blocks = []
    for p in paths:
        content = _read_clone_file(repo_path, p)
        if content:
            file_blocks.append(f"=== {p} ===\n{content}")
    tree = await get_repo_tree_summary(owner, repo, token)
    logger.info(f"[fix_issue] context: {len(file_blocks)} files, tree {len(tree.splitlines())} lines")
    await _emit(progress, "analyze", f"Read {len(file_blocks)} relevant file(s)")

    # 4) Ask Claude to plan the changes (with screenshots)
    await _emit(progress, "plan", "Writing the fix with Claude")
    text_prompt = (
        f"ISSUE #{issue['number']}: {issue['title']}\n\n"
        f"DESCRIPTION:\n{issue.get('body_full') or issue.get('body','')}\n\n"
        f"LABELS: {', '.join(l['name'] for l in issue.get('labels', [])) or 'none'}\n\n"
        f"REPO FILE TREE:\n{tree}\n\n"
        f"RELEVANT SOURCE FILES:\n\n" + "\n\n".join(file_blocks) +
        "\n\nNow resolve the issue. Return STRICT JSON as instructed."
    )
    content = [{"type": "text", "text": text_prompt}] + await _image_blocks(issue, token)

    client = get_client(key)
    msg = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=16000,   # full file bodies can be large — avoid truncation
        system=_SYSTEM,
        messages=[{"role": "user", "content": content}],
    )
    raw = msg.content[0].text
    cost_inr = round(
        (msg.usage.input_tokens * _SONNET_IN_PRICE + msg.usage.output_tokens * _SONNET_OUT_PRICE) * _USD_TO_INR, 4
    )
    logger.info(f"[fix_issue] Claude: in={msg.usage.input_tokens} out={msg.usage.output_tokens} stop={msg.stop_reason} cost=₹{cost_inr}")

    try:
        plan = _parse_changes(raw)
        changes = plan.get("changes") or []
        summary = plan.get("summary") or "AI-generated fix."
    except Exception as e:
        logger.error(f"[fix_issue] could not parse plan: {e}\n--- raw head ---\n{raw[:400]}")
        return {"success": False, "error": "The model didn't return a valid change set.", "cost_inr": cost_inr}

    if msg.stop_reason == "max_tokens" and not changes:
        return {"success": False, "error": "The fix was too large to generate in one pass. Try a more specific issue.", "cost_inr": cost_inr}

    if not changes:
        return {"success": False, "error": "No code changes were proposed for this issue.", "cost_inr": cost_inr}

    # 5) Write the changes into the clone
    await _emit(progress, "write", f"Applying {len(changes)} file change(s)")
    written = []
    for ch in changes:
        full = _safe_join(repo_path, ch.get("path", ""))
        if not full or "content" not in ch:
            continue
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as f:
            f.write(ch["content"])
        written.append(ch["path"])
    if not written:
        return {"success": False, "error": "Proposed changes had no valid file paths.", "cost_inr": cost_inr}

    # 6) Branch, commit, push, PR — via the reusable open_pr helper.
    await _emit(progress, "pr", "Committing, pushing and opening the pull request")
    branch = f"ai-fix/issue-{issue_number}-{int(time.time())}"
    pr_body = (
        f"Generated by the AI assistant to resolve **issue #{issue_number}**.\n\n"
        f"**Issue:** {issue['title']}\n{issue['url']}\n\n"
        f"**What changed:**\n{summary}\n\n"
        f"**Files:**\n" + "\n".join(f"- `{p}`" for p in written) +
        f"\n\nFixes #{issue_number}\n\n> 🤖 AI-generated — review carefully before merging."
    )
    try:
        pr_url, branch = await open_pr(
            repo_path, branch,
            commit_message=f"fix: resolve issue #{issue_number} — {issue['title'][:60]}",
            title=f"AI fix: #{issue_number} {issue['title'][:70]}",
            body=pr_body, owner=owner, repo=repo, token=token, base=base_branch,
            paths=written,   # stage ONLY the files we changed — no graph/build artifacts
        )
    except NoChangesError:
        return {"success": False, "error": "The proposed changes were identical to the existing code.", "cost_inr": cost_inr}

    logger.info(f"[fix_issue] PR opened: {pr_url}")
    return {"success": True, "pr_url": pr_url, "branch": branch, "summary": summary, "files": written, "cost_inr": cost_inr}
