"""Core assistant orchestration: intent → graph context → routed reply.

Shared by the /api/message/, /api/chat/ routes and the WhatsApp webhook so the
classification + routing logic lives in exactly one place.
"""
from server.agents.intent_parser import parse_intent, generate_chat_reply, calc_cost_inr
from server.agents.status_agent import handle_status_query
from server.services.graph_service import graph_exists, query_graph, relevant_files
from server.services.commands import resolve_and_set_repo
from server.adapters.github_adapter import (
    search_files_in_repo, get_repo_tree_summary, get_file_content, search_code_in_repo,
)
from server.utils.credentials import github_token, openai_key
from server.utils.logger import logger

_STOP_WORDS = {
    'the', 'is', 'in', 'on', 'at', 'to', 'a', 'an', 'and', 'or', 'for', 'of',
    'with', 'how', 'what', 'where', 'give', 'me', 'tell', 'my', 'have', 'this',
    'that', 'many', 'does', 'do', 'i', 'you', 'code', 'base', 'codebase',
    'project', 'repo', 'which', 'flow', 'flows', 'about', 'can', 'all', 'are',
}

_NO_REPO_MSG = (
    "No repository is connected for this chat.\n"
    "Use !repos to list available repos, then !repo owner/name to pick one."
)

import re

# ── Deterministic ordinal resolution ─────────────────────────────────────────
# LLMs miscount "the 4th one"; resolve it in code from the last list we showed.
_ORDINALS = {
    "first": 1, "1st": 1, "second": 2, "2nd": 2, "third": 3, "3rd": 3,
    "fourth": 4, "4th": 4, "fifth": 5, "5th": 5, "sixth": 6, "6th": 6,
    "seventh": 7, "7th": 7, "eighth": 8, "8th": 8, "ninth": 9, "9th": 9,
    "tenth": 10, "10th": 10,
}


def _last_id_of_kind(history: list, kind: str):
    """Most recent id for a specific kind ('issues'|'prs'), from a list (its
    *#N* markers) or a detail header (*Issue #N:* / *PR #N:*). Crucially it does
    NOT scrape numbers out of bodies — so a PR whose body mentions 'issue #21'
    is never mistaken for an issue, and a PR number is never read as an issue."""
    header = "open issues" if kind == "issues" else "open prs"
    detail = r"\*issue #(\d+)" if kind == "issues" else r"\*pr #(\d+)"
    for h in reversed(history or []):
        if h.get("role") != "assistant":
            continue
        c = str(h.get("content", ""))
        cl = c.lower()
        if header in cl:                       # a list of this kind
            ids = re.findall(r"\*#(\d+)\*", c)
            if ids:
                return int(ids[0])
        m = re.search(detail, cl)              # a detail header of this kind
        if m:
            return int(m.group(1))
    return None


def _ordinal_in(message: str):
    """Return 1-based position, -1 for 'last', or None."""
    m = (message or "").lower()
    if re.search(r"\blast\b", m):
        return -1
    for word, n in _ORDINALS.items():
        if re.search(rf"\b{word}\b", m):
            return n
    return None


def _desired_kind(message: str):
    """What the user explicitly asked for: 'prs' | 'commits' | 'issues' | None."""
    m = (message or "").lower()
    if "pull request" in m or re.search(r"\bprs?\b", m):
        return "prs"
    if re.search(r"\bcommits?\b", m):
        return "commits"
    if re.search(r"\bissues?\b", m):
        return "issues"
    return None


def _find_list(history: list, want_kind):
    """Most recent LIST message (matched by its header) → (kind, [ids in order]).

    Only considers list messages (by header), and reads the bolded list-item
    markers — so numbers inside titles/bodies (e.g. 'AI fix: #21') are ignored.
    """
    for h in reversed(history or []):
        if h.get("role") != "assistant":
            continue
        c = str(h.get("content", ""))
        cl = c.lower()
        if "open prs" in cl:
            kind = "prs"
        elif "open issues" in cl:
            kind = "issues"
        elif "recent commits" in cl:
            kind = "commits"
        else:
            continue  # not a list message
        if want_kind and kind != want_kind:
            continue
        if kind == "commits":
            ids = re.findall(r"`([0-9a-f]{7,40})`", c)
        else:
            ids = re.findall(r"\*#(\d+)\*", c)  # only the *#N* list-item markers
        if ids:
            return kind, ids
    return None, []


def _resolve_ordinal(message: str, history: list, intent: dict) -> None:
    """If the user says 'the Nth one' / 'the last one', override the entity id
    deterministically from the matching list (don't trust the LLM's count)."""
    n = _ordinal_in(message)
    if n is None:
        return
    kind, ids = _find_list(history, _desired_kind(message))
    if not ids:
        return
    idx = (n - 1) if n > 0 else (len(ids) - 1)
    if not (0 <= idx < len(ids)):
        return
    ent = intent.setdefault("entities", {})
    if kind == "commits":
        ent["commit_sha"], ent["query_type"] = ids[idx], "commit_detail"
    elif kind == "prs":
        ent["pr_number"], ent["query_type"] = int(ids[idx]), "pr_detail"
    elif kind == "issues":
        ent["issue_number"], ent["query_type"] = int(ids[idx]), "issue_detail"


_DEPTH_RE = re.compile(
    r"\b(in[\s-]?depth|deep(ly|er)?|exhaustive|line[\s-]?by[\s-]?line|"
    r"function[\s-]?by[\s-]?function|every (variable|line|detail)|"
    r"full (trace|walkthrough)|trace (it )?exactly|ocean)\b",
    re.IGNORECASE,
)


def _wants_depth(message: str) -> bool:
    return bool(_DEPTH_RE.search(message or ""))


async def run_assistant(
    message: str,
    owner: str,
    repo: str,
    history: list | None = None,
    technical: bool = False,
    intent: dict | None = None,
    ctx: dict | None = None,
    progress=None,
) -> dict:
    """Returns {reply, intent, data, cost_inr, graph_used}. `progress` (async cb)
    receives {stage, message} events for a live loader."""
    usage_acc: dict = {}
    history = history or []
    token = github_token()

    async def emit(stage, msg):
        if progress:
            try:
                await progress({"stage": stage, "message": msg})
            except Exception:
                pass

    # Intent classification uses OpenAI (gpt-4o-mini); chat replies use Claude.
    if intent is None:
        await emit("intent", "Understanding your question")
        intent = await parse_intent(message, api_key=openai_key(), history=history, usage_acc=usage_acc)
    detected = intent.get("intent", "unknown")

    # Natural-language repo switching — actually perform it (don't let the LLM pretend).
    if detected == "repo_switch":
        ent = intent.get("entities", {})
        if ctx is not None:
            reply = await resolve_and_set_repo(ctx, ent.get("owner") or "", ent.get("repo") or "")
        else:
            reply = "To switch repos, use the !repo owner/name command."
        cost_inr = calc_cost_inr(usage_acc) if usage_acc else None
        return {"reply": reply, "intent": detected, "data": None, "cost_inr": cost_inr, "graph_used": False}

    # Auto-fix an issue → hand a trigger back to the bridge (the actual clone +
    # codegen + PR runs via /api/fix-issue/, which the bridge calls with a loader).
    if detected == "fix_issue":
        ent = intent.get("entities", {})
        cost = calc_cost_inr(usage_acc) if usage_acc else None
        # Auto-fix targets ISSUES only. "fix this PR" is invalid — a PR is already a fix.
        if _desired_kind(message) == "prs":
            return {"reply": "Auto-fix works on *issues*, not pull requests — a PR is already a proposed fix. "
                             "Tell me an issue to fix, e.g. *fix issue 21*.",
                    "intent": "fix_issue", "data": None, "cost_inr": cost, "graph_used": False}
        # Resolve the issue number: explicit > issue-context from history (never a PR).
        issue_number = ent.get("issue_number") or _last_id_of_kind(history, "issues")
        if not owner or not repo:
            reply, data = _NO_REPO_MSG, None
        elif not issue_number:
            reply, data = "Which issue should I fix? Tell me the number, e.g. *fix issue 21*.", None
        else:
            reply = f"🛠 Starting an auto-fix for issue #{int(issue_number)}…"
            data = {"type": "fix_issue", "owner": owner, "repo": repo, "issue_number": int(issue_number)}
        return {"reply": reply, "intent": "fix_issue", "data": data, "cost_inr": cost, "graph_used": False}

    # "the 4th one" / "the last one" → resolve the id deterministically from history.
    if detected == "status_query":
        _resolve_ordinal(message, history, intent)

    needs_graph = intent.get("needs_graph", False) or detected == "code_question"
    deep = technical and _wants_depth(message)  # only dump full source on explicit "in depth"
    data = None
    graph_used = False

    # Fetch graph context when the question is about the codebase
    graph_ctx = ""
    if needs_graph and owner and repo:
        await emit("context", "Looking up the codebase")
        if graph_exists(owner, repo):
            graph_ctx = query_graph(owner, repo, message)
            graph_used = bool(graph_ctx)
            logger.info(f"[assistant] graph context: {len(graph_ctx)} chars")
        else:
            # No graph yet — provide a 2-level repo tree so Claude has real context
            tree_summary = await get_repo_tree_summary(owner, repo, token)

            terms = [
                t.lower() for t in message.split()
                if len(t) > 3 and t.lower() not in _STOP_WORDS
            ]
            seen_paths: set = set()
            tree_matches = []
            for term in terms[:4]:
                for m in await search_files_in_repo(owner, repo, term, token, max_results=6):
                    if m["path"] not in seen_paths:
                        seen_paths.add(m["path"])
                        tree_matches.append(m)

            ctx_parts = [tree_summary]
            if tree_matches:
                match_lines = ["\nFiles specifically matching your query terms:"]
                for m in tree_matches[:12]:
                    match_lines.append(f"  {'📁' if m['type']=='directory' else '📄'} {m['path']}")
                ctx_parts.append("\n".join(match_lines))
            ctx_parts.append("\n(Run !graph build for deeper codebase analysis)")

            graph_ctx = "\n".join(ctx_parts)
            graph_used = bool(tree_summary)
            logger.info(f"[assistant] tree fallback: {len(tree_summary.splitlines())} lines, {len(tree_matches)} matches")

        # Deep technical mode: pull the ACTUAL source of the most relevant files
        # so the model can trace exact functions, params, and variable changes.
        # Read the actual source for technical code questions so the flow/order is
        # accurate (not guessed). Deep mode pulls more/larger files than moderate.
        if technical and detected == "code_question" and token:
            terms2 = [t.lower() for t in message.split() if len(t) > 3 and t.lower() not in _STOP_WORDS]
            files: list[str] = []

            # 1) Graph: term-relevant files, or the repo's CORE files when the user's
            #    wording isn't in the code (e.g. "translate flow" → sqlStore.ts).
            if graph_exists(owner, repo):
                for p in relevant_files(owner, repo, message, limit=6):
                    if p not in files:
                        files.append(p)
            # 2) Content search — catches files that mention the concept verbatim.
            if terms2:
                for p in await search_code_in_repo(owner, repo, " ".join(terms2[:5]), token, max_results=6):
                    if p not in files:
                        files.append(p)
            # 3) Last resort: filename search.
            if not files:
                for term in terms2[:4]:
                    for m in await search_files_in_repo(owner, repo, term, token, max_results=4):
                        if m["type"] == "file" and m["path"] not in files:
                            files.append(m["path"])

            n_files = 5 if deep else 3
            max_chars = 20000 if deep else 14000
            blocks = []
            for fp in files[:n_files]:
                content = await get_file_content(owner, repo, fp, token, max_chars=max_chars)
                if content:
                    blocks.append(f"=== {fp} ===\n{content}")
            if blocks:
                graph_ctx = (graph_ctx + "\n\n" if graph_ctx else "") + \
                    "ACTUAL SOURCE CODE OF RELEVANT FILES (use this to trace the real flow/order):\n\n" + "\n\n".join(blocks)
                graph_used = True
                await emit("context", f"Read {len(blocks)} relevant file(s)")
                logger.info(f"[assistant] {'deep' if deep else 'flow'} mode: attached {len(blocks)} source file(s): {files[:n_files]}")

    if detected == "status_query":
        if not token or not owner or not repo:
            reply, data = _NO_REPO_MSG, {"type": "empty", "message": _NO_REPO_MSG}
        else:
            await emit("fetch", "Fetching the latest from GitHub")
            reply, data = await handle_status_query(intent, token, owner, repo)

    elif detected == "code_question":
        await emit("answer", "Writing the answer")
        reply = await generate_chat_reply(
            message, owner, repo, api_key=openai_key(), history=history,
            usage_acc=usage_acc, graph_context=graph_ctx,
            is_code_question=True, technical_mode=technical, deep=deep,
        )

    elif detected == "general_chat":
        await emit("answer", "Writing the answer")
        reply = await generate_chat_reply(
            message, owner, repo, api_key=openai_key(), history=history,
            usage_acc=usage_acc, graph_context=graph_ctx, technical_mode=technical,
        )

    elif detected == "feature_request":
        reply = f"Feature request noted: {intent.get('summary', message)}\n\nAuto-implementation is coming in Phase 2!"

    elif detected == "bug_report":
        reply = f"Bug report noted: {intent.get('summary', message)}\n\nUse the Error Fix tab to trigger the auto-fix pipeline."

    elif detected == "approval":
        reply = "Approval/rejection flows are coming in Phase 2!"

    else:
        reply = await generate_chat_reply(
            message, owner, repo, api_key=openai_key(), history=history,
            usage_acc=usage_acc, graph_context=graph_ctx, technical_mode=technical,
        )

    cost_inr = calc_cost_inr(usage_acc) if usage_acc else None
    return {"reply": reply, "intent": detected, "data": data, "cost_inr": cost_inr, "graph_used": graph_used}
