from __future__ import annotations

import asyncio
import base64
import re
import time
import httpx
from typing import Optional
from server.utils.logger import logger

_BASE = "https://api.github.com"
_RATE_LOCK = asyncio.Lock()
_last_call: float = 0.0
_MIN_INTERVAL = 0.5  # 2 req/sec max


async def _throttled_get(url: str, token: str, params: Optional[dict] = None) -> dict:
    global _last_call
    async with _RATE_LOCK:
        now = time.monotonic()
        wait = _MIN_INTERVAL - (now - _last_call)
        if wait > 0:
            await asyncio.sleep(wait)
        _last_call = time.monotonic()

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    logger.info(f"[github_adapter] GET {url}")
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(url, headers=headers, params=params)
        resp.raise_for_status()
        return resp.json()


async def _throttled_request(method: str, url: str, token: str,
                             json: Optional[dict] = None) -> httpx.Response:
    """Rate-limited write request (PATCH/PUT/DELETE/POST). Returns the raw
    response so callers can branch on status (e.g. 405 = PR not mergeable)
    without an exception. Shares the same throttle as `_throttled_get`."""
    global _last_call
    async with _RATE_LOCK:
        now = time.monotonic()
        wait = _MIN_INTERVAL - (now - _last_call)
        if wait > 0:
            await asyncio.sleep(wait)
        _last_call = time.monotonic()

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    logger.info(f"[github_adapter] {method} {url}")
    async with httpx.AsyncClient(timeout=20) as client:
        return await client.request(method, url, headers=headers, json=json)


async def list_user_repos(token: str, max_repos: int = 200) -> list[dict]:
    """All repos the token can access, most-recently-updated first (paginated).

    Note: which repos are visible depends on the token's scopes — `public_repo`
    sees only public repos; full `repo` is needed for private repos.
    """
    repos: list[dict] = []
    page = 1
    per_page = 100
    while len(repos) < max_repos:
        data = await _throttled_get(
            f"{_BASE}/user/repos", token,
            {"per_page": per_page, "page": page, "sort": "updated",
             "affiliation": "owner,collaborator,organization_member"},
        )
        if not data:
            break
        repos.extend(data)
        if len(data) < per_page:
            break
        page += 1
    return [
        {
            "full_name": r["full_name"],
            "name":      r["name"],
            "owner":     r["owner"]["login"],
            "private":   r.get("private", False),
            "url":       r["html_url"],
        }
        for r in repos[:max_repos]
    ]


async def repo_exists(owner: str, repo: str, token: str) -> bool:
    try:
        await _throttled_get(f"{_BASE}/repos/{owner}/{repo}", token)
        return True
    except Exception:
        return False


async def get_open_prs(owner: str, repo: str, token: str) -> list[dict]:
    data = await _throttled_get(f"{_BASE}/repos/{owner}/{repo}/pulls", token, {"state": "open", "per_page": 10})
    return [{"number": pr["number"], "title": pr["title"], "author": pr["user"]["login"], "url": pr["html_url"]} for pr in data]


async def get_pr(owner: str, repo: str, pr_number: int, token: str) -> dict:
    data = await _throttled_get(f"{_BASE}/repos/{owner}/{repo}/pulls/{pr_number}", token)

    # GitHub computes `mergeable` asynchronously, so it's often null on the first
    # read of an open PR. Re-fetch a few times until it settles so the bridge can
    # reliably decide whether to show the "Merge with main" button.
    mergeable = data.get("mergeable")
    if mergeable is None and data.get("state") == "open" and not data.get("merged"):
        for _ in range(3):
            await asyncio.sleep(1.0)
            data = await _throttled_get(f"{_BASE}/repos/{owner}/{repo}/pulls/{pr_number}", token)
            mergeable = data.get("mergeable")
            if mergeable is not None:
                break

    head = data.get("head") or {}
    return {
        "owner": owner,
        "repo": repo,
        "number": data["number"],
        "title": data["title"],
        "state": data["state"],
        "author": data["user"]["login"],
        "url": data["html_url"],
        "body": (data.get("body") or "")[:500],
        "merged": data.get("merged", False),
        "draft": data.get("draft", False),
        # mergeable: True = no conflicts, False = conflicts, None = undetermined.
        "mergeable": mergeable,
        "mergeable_state": data.get("mergeable_state"),  # clean|dirty|blocked|behind|…
        "head_ref": head.get("ref"),
        # head repo may differ (fork) — only safe to delete a branch in our own repo.
        "head_repo_full_name": (head.get("repo") or {}).get("full_name"),
    }


async def get_open_issues(owner: str, repo: str, token: str) -> list[dict]:
    data = await _throttled_get(
        f"{_BASE}/repos/{owner}/{repo}/issues", token,
        {"state": "open", "per_page": 10, "pulls": "false"}
    )
    # GitHub issues endpoint includes PRs; filter them out
    issues = [i for i in data if "pull_request" not in i]
    return [{"number": i["number"], "title": i["title"], "author": i["user"]["login"], "url": i["html_url"]} for i in issues]


async def get_recent_commits(owner: str, repo: str, token: str, count: int = 5) -> list[dict]:
    data = await _throttled_get(f"{_BASE}/repos/{owner}/{repo}/commits", token, {"per_page": count})
    return [{"sha": c["sha"][:7], "message": c["commit"]["message"].split("\n")[0], "author": c["commit"]["author"]["name"]} for c in data]


def _extract_images(text: str) -> list[str]:
    """Image URLs from markdown ![](url) AND HTML <img src="url"> in issue/PR bodies."""
    if not text:
        return []
    md = re.findall(r'!\[.*?\]\((https?://[^)\s]+)\)', text)
    html = re.findall(r'<img[^>]+src=["\']?(https?://[^"\'>\s]+)', text, re.IGNORECASE)
    out: list[str] = []
    for u in md + html:
        if u not in out:
            out.append(u)
    return out


def _strip_images(text: str) -> str:
    """Remove image markup so the displayed text doesn't show raw <img> tags / md."""
    if not text:
        return text
    text = re.sub(r'!\[.*?\]\(https?://[^)\s]+\)', '', text)
    text = re.sub(r'<img[^>]*>', '', text, flags=re.IGNORECASE)
    return re.sub(r'\n{3,}', '\n\n', text).strip()


async def fetch_image_bytes(url: str, token: str, max_bytes: int = 6_000_000) -> tuple[bytes, str] | None:
    """Download image bytes (+ mime) — for passing screenshots to Claude vision."""
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            r = await client.get(url, headers={"Authorization": f"Bearer {token}"})
        if r.status_code != 200:
            return None
        ct = r.headers.get("content-type", "").split(";")[0]
        if not ct.startswith("image/") or len(r.content) > max_bytes:
            return None
        return r.content, ct
    except Exception as e:
        logger.error(f"[github_adapter] image bytes fetch failed: {e}")
        return None


async def resolve_image_url(url: str, token: str) -> str:
    """Turn an auth-gated GitHub image URL into a publicly-fetchable one.

    `github.com/user-attachments/assets/...` 404s without a GitHub session, but
    it 302-redirects (with the token) to a SIGNED S3 URL that anyone can fetch —
    which is exactly what Slack needs for an image block. Other URLs are returned
    as-is (already public).
    """
    if "user-attachments/assets" not in url:
        return url
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=False) as client:
            r = await client.get(url, headers={"Authorization": f"Bearer {token}"})
        loc = r.headers.get("location")
        if r.status_code in (301, 302, 303, 307, 308) and loc:
            return loc
        return url
    except Exception as e:
        logger.error(f"[github_adapter] image resolve failed: {e}")
        return url


async def get_issue_detail(owner: str, repo: str, issue_number: int, token: str) -> dict:
    data = await _throttled_get(f"{_BASE}/repos/{owner}/{repo}/issues/{issue_number}", token)
    comments_data = await _throttled_get(
        f"{_BASE}/repos/{owner}/{repo}/issues/{issue_number}/comments", token, {"per_page": 10}
    )
    body = data.get("body") or ""
    images = _extract_images(body)
    body = _strip_images(body)   # show clean text; images render separately

    comments = []
    for c in comments_data[:5]:
        raw_c = c.get("body") or ""
        c_images = _extract_images(raw_c)
        comments.append({
            "author": c["user"]["login"],
            "body": _strip_images(raw_c)[:400],
            "date": c["created_at"],
            "images": c_images,
        })
        images.extend(c_images)

    images = list(dict.fromkeys(images))
    # Resolve auth-gated GitHub URLs to public signed URLs Slack can fetch.
    images = [await resolve_image_url(u, token) for u in images[:5]]

    return {
        "owner": owner,
        "repo": repo,
        "number": data["number"],
        "title": data["title"],
        "state": data["state"],
        "author": data["user"]["login"],
        "url": data["html_url"],
        "body": body[:800],
        "body_full": _strip_images(data.get("body") or "")[:6000],
        "labels": [{"name": l["name"], "color": l["color"]} for l in data.get("labels", [])],
        "images": images,
        "comments_count": data.get("comments", 0),
        "comments": comments,
    }


async def search_files_in_repo(owner: str, repo: str, term: str, token: str, max_results: int = 10) -> list[dict]:
    """Search the ENTIRE repo tree recursively for files/folders matching a term."""
    try:
        repo_data = await _throttled_get(f"{_BASE}/repos/{owner}/{repo}", token)
        branch = repo_data.get("default_branch", "main")
        tree_data = await _throttled_get(
            f"{_BASE}/repos/{owner}/{repo}/git/trees/{branch}",
            token,
            {"recursive": "1"},
        )
        term_lower = term.lower()
        matches = []
        for item in tree_data.get("tree", []):
            path = item.get("path", "")
            name = path.split("/")[-1].lower()
            if term_lower in name:
                matches.append({
                    "path": path,
                    "type": "directory" if item.get("type") == "tree" else "file",
                    "name": path.split("/")[-1],
                })
            if len(matches) >= max_results:
                break
        return matches
    except Exception as e:
        logger.error(f"[github_adapter] search_files_in_repo failed: {e}")
        return []


async def get_file_or_dir(owner: str, repo: str, path: str, token: str) -> dict:
    """Returns directory listing or file content from the repo tree."""
    clean = path.strip("/").strip()
    try:
        data = await _throttled_get(f"{_BASE}/repos/{owner}/{repo}/contents/{clean}", token)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            # Recursive whole-repo search — finds nested files like src/stores/sqlStore.ts
            leaf = clean.split("/")[-1]
            matches = await search_files_in_repo(owner, repo, leaf, token, max_results=8)
            return {"kind": "not_found", "path": clean, "matches": matches,
                    "suggestions": [m["path"] for m in matches]}
        raise

    if isinstance(data, list):
        # Directory
        files = [
            {
                "name":  item["name"],
                "type":  item["type"],          # "file" | "dir"
                "size":  item.get("size", 0),
                "url":   item["html_url"],
            }
            for item in data[:30]
        ]
        return {
            "kind":  "directory",
            "path":  path,
            "url":   f"https://github.com/{owner}/{repo}/tree/HEAD/{path}",
            "files": files,
        }
    else:
        # Single file — decode content
        content = ""
        if data.get("encoding") == "base64" and data.get("content"):
            raw = base64.b64decode(data["content"]).decode("utf-8", errors="ignore")
            content = raw[:2000]
        return {
            "kind":    "file",
            "path":    path,
            "name":    data.get("name", path.split("/")[-1]),
            "size":    data.get("size", 0),
            "url":     data.get("html_url", ""),
            "content": content,
        }


async def search_code_in_repo(owner: str, repo: str, query: str, token: str, max_results: int = 5) -> list[str]:
    """Search file CONTENTS (GitHub code search) — finds files mentioning the terms,
    not just files named after them. Returns matching file paths."""
    q = f"{query} repo:{owner}/{repo}"
    try:
        data = await _throttled_get(f"{_BASE}/search/code", token, {"q": q, "per_page": max_results})
    except Exception as e:
        logger.error(f"[github_adapter] code search failed: {e}")
        return []
    seen: list[str] = []
    for item in data.get("items", []):
        p = item.get("path")
        if p and p not in seen:
            seen.append(p)
        if len(seen) >= max_results:
            break
    return seen


async def get_file_content(owner: str, repo: str, path: str, token: str, max_chars: int = 16000) -> str:
    """Full(ish) source of a single file — for deep code analysis (not truncated to 2k)."""
    clean = path.strip("/").strip()
    try:
        data = await _throttled_get(f"{_BASE}/repos/{owner}/{repo}/contents/{clean}", token)
    except Exception:
        return ""
    if isinstance(data, list):
        return ""  # directory, not a file
    if data.get("encoding") == "base64" and data.get("content"):
        raw = base64.b64decode(data["content"]).decode("utf-8", errors="ignore")
        return raw[:max_chars]
    return ""


async def get_repo_tree_summary(owner: str, repo: str, token: str, max_depth: int = 2) -> str:
    """Single API call → compact 2-level repo structure string for Claude context."""
    try:
        repo_data = await _throttled_get(f"{_BASE}/repos/{owner}/{repo}", token)
        branch = repo_data.get("default_branch", "main")
        lang = repo_data.get("language") or "unknown"

        tree_data = await _throttled_get(
            f"{_BASE}/repos/{owner}/{repo}/git/trees/{branch}",
            token,
            {"recursive": "1"},
        )

        lines = [f"[{owner}/{repo}] language={lang} branch={branch}"]
        count = 0
        for item in tree_data.get("tree", []):
            path = item.get("path", "")
            if path.count("/") >= max_depth:
                continue
            icon = "📁" if item.get("type") == "tree" else "📄"
            lines.append(f"{icon} {path}")
            count += 1
            if count >= 120:
                lines.append("... (truncated)")
                break
        return "\n".join(lines)
    except Exception as e:
        logger.error(f"[github_adapter] get_repo_tree_summary failed: {e}")
        return ""


async def get_repo_info(owner: str, repo: str, token: str) -> dict:
    data = await _throttled_get(f"{_BASE}/repos/{owner}/{repo}", token)

    # README — best-effort
    readme_excerpt = ""
    try:
        readme_data = await _throttled_get(f"{_BASE}/repos/{owner}/{repo}/readme", token)
        raw = base64.b64decode(readme_data.get("content", "")).decode("utf-8", errors="ignore")
        # Drop markdown headings and blank lines, grab first ~400 useful chars
        lines = [l.strip() for l in raw.splitlines() if l.strip() and not l.startswith("#") and not l.startswith("---")]
        readme_excerpt = " ".join(lines)[:400]
    except Exception:
        pass

    # Top-level file/folder tree — best-effort
    top_files: list[str] = []
    try:
        branch = data.get("default_branch", "main")
        tree = await _throttled_get(f"{_BASE}/repos/{owner}/{repo}/git/trees/{branch}", token)
        top_files = [item["path"] for item in tree.get("tree", [])[:20]]
    except Exception:
        pass

    return {
        "name":           data["name"],
        "full_name":      data["full_name"],
        "description":    data.get("description") or "",
        "language":       data.get("language") or "Unknown",
        "stars":          data.get("stargazers_count", 0),
        "forks":          data.get("forks_count", 0),
        "open_issues":    data.get("open_issues_count", 0),
        "default_branch": data.get("default_branch", "main"),
        "topics":         data.get("topics", []),
        "pushed_at":      data.get("pushed_at"),
        "created_at":     data.get("created_at"),
        "url":            data["html_url"],
        "private":        data.get("private", False),
        "license":        (data.get("license") or {}).get("name", ""),
        "readme_excerpt": readme_excerpt,
        "top_files":      top_files,
    }


# ── Write operations (issue/PR lifecycle) ────────────────────────────────────

async def close_issue(owner: str, repo: str, issue_number: int, token: str) -> dict:
    """Mark an issue as fixed → close it with state_reason=completed."""
    resp = await _throttled_request(
        "PATCH", f"{_BASE}/repos/{owner}/{repo}/issues/{issue_number}", token,
        json={"state": "closed", "state_reason": "completed"},
    )
    if resp.status_code >= 400:
        raise RuntimeError(f"GitHub {resp.status_code}: {resp.text[:200]}")
    data = resp.json()
    return {"number": data["number"], "state": data["state"], "url": data["html_url"]}


async def delete_issue(owner: str, repo: str, issue_number: int, token: str) -> dict:
    """Permanently delete an issue. The REST API has no delete-issue endpoint —
    this uses the GraphQL `deleteIssue` mutation (requires admin on the repo)."""
    # Fetch the issue's GraphQL node id (REST issue payload includes `node_id`).
    issue = await _throttled_get(f"{_BASE}/repos/{owner}/{repo}/issues/{issue_number}", token)
    node_id = issue.get("node_id")
    if not node_id:
        raise RuntimeError("Could not resolve issue node id for deletion")

    query = "mutation($id: ID!) { deleteIssue(input: {issueId: $id}) { clientMutationId } }"
    resp = await _throttled_request(
        "POST", f"{_BASE}/graphql", token,
        json={"query": query, "variables": {"id": node_id}},
    )
    if resp.status_code >= 400:
        raise RuntimeError(f"GitHub {resp.status_code}: {resp.text[:200]}")
    body = resp.json()
    if body.get("errors"):
        msg = body["errors"][0].get("message", "deletion failed")
        raise RuntimeError(msg)
    return {"number": issue_number, "deleted": True}


async def merge_pr(owner: str, repo: str, pr_number: int, token: str) -> dict:
    """Merge a PR into its base branch. Returns {merged, message}. A 405/409
    means GitHub refused (conflicts / not mergeable) — surfaced, not raised."""
    resp = await _throttled_request(
        "PUT", f"{_BASE}/repos/{owner}/{repo}/pulls/{pr_number}/merge", token,
        json={"merge_method": "merge"},
    )
    if resp.status_code == 200:
        data = resp.json()
        return {"merged": True, "message": data.get("message", "Merged"), "sha": data.get("sha")}
    # 405 = not mergeable, 409 = head changed / conflict, 403 = no permission.
    try:
        reason = resp.json().get("message", resp.text[:200])
    except Exception:
        reason = resp.text[:200]
    return {"merged": False, "message": reason, "status": resp.status_code}


async def close_pr(owner: str, repo: str, pr_number: int, token: str,
                   delete_branch: bool = True) -> dict:
    """Close a PR (PRs can't be REST-deleted) and, when safe, delete its head
    branch — the closest equivalent to 'delete PR'. Skips branch deletion for
    forks and the default branch."""
    pr = await get_pr(owner, repo, pr_number, token)
    resp = await _throttled_request(
        "PATCH", f"{_BASE}/repos/{owner}/{repo}/pulls/{pr_number}", token,
        json={"state": "closed"},
    )
    if resp.status_code >= 400:
        raise RuntimeError(f"GitHub {resp.status_code}: {resp.text[:200]}")

    branch_deleted = False
    head_ref = pr.get("head_ref")
    repo_data = await _throttled_get(f"{_BASE}/repos/{owner}/{repo}", token)
    default_branch = repo_data.get("default_branch", "main")
    same_repo = pr.get("head_repo_full_name") == f"{owner}/{repo}"
    if delete_branch and head_ref and same_repo and head_ref != default_branch:
        del_resp = await _throttled_request(
            "DELETE", f"{_BASE}/repos/{owner}/{repo}/git/refs/heads/{head_ref}", token,
        )
        branch_deleted = del_resp.status_code in (200, 204)

    return {"number": pr_number, "closed": True, "branch": head_ref, "branch_deleted": branch_deleted}


async def get_commit(owner: str, repo: str, sha: str, token: str) -> dict:
    data = await _throttled_get(f"{_BASE}/repos/{owner}/{repo}/commits/{sha}", token)
    commit = data["commit"]
    stats = data.get("stats", {})
    files = data.get("files", [])
    return {
        "sha": data["sha"][:7],
        "sha_full": data["sha"],
        "message": commit["message"],
        "author": commit["author"]["name"],
        "author_email": commit["author"]["email"],
        "date": commit["author"]["date"],
        "url": data["html_url"],
        "additions": stats.get("additions", 0),
        "deletions": stats.get("deletions", 0),
        "total_changes": stats.get("total", 0),
        "files": [
            {
                "filename": f["filename"],
                "status": f["status"],
                "additions": f.get("additions", 0),
                "deletions": f.get("deletions", 0),
                "patch": (f.get("patch") or "")[:600],
            }
            for f in files[:10]
        ],
    }
