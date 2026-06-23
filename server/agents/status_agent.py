from server.adapters.github_adapter import (
    get_open_prs, get_open_issues, get_recent_commits,
    get_pr, get_commit, get_issue_detail, get_repo_info, get_file_or_dir,
    search_files_in_repo,
)
from server.utils.logger import logger


async def handle_status_query(intent: dict, github_token: str, owner: str, repo: str) -> tuple[str, dict]:
    """Returns (plain_text_fallback, structured_data) tuple."""
    entities     = intent.get("entities", {})
    query_type   = entities.get("query_type")
    modifier     = entities.get("modifier")        # "count" | "latest" | None
    pr_number    = entities.get("pr_number")
    commit_sha   = entities.get("commit_sha")
    issue_number = entities.get("issue_number")
    file_path    = entities.get("file_path")

    # A "detail" query with no concrete id → degrade to the matching LIST,
    # so "tell me about the issue I have" lists issues instead of falling through to PRs.
    if query_type == "issue_detail" and not issue_number:
        query_type = "issues"
    elif query_type == "commit_detail" and not commit_sha:
        query_type = "commits"
    elif query_type == "pr_detail" and not pr_number:
        query_type = "prs"

    try:
        # ── File / folder explorer ───────────────────────────────────
        if query_type == "file_query" and file_path:
            d = await get_file_or_dir(owner, repo, file_path, github_token)

            if d["kind"] == "not_found":
                matches = d.get("matches", [])
                if len(matches) == 1:
                    # Single unambiguous match — auto-navigate silently
                    d = await get_file_or_dir(owner, repo, matches[0]["path"], github_token)
                    file_path = matches[0]["path"]
                    # fall through to directory/file handling below
                elif matches:
                    msg = f"No exact match for '{file_path}'. Found {len(matches)} similar:"
                    return (
                        msg,
                        {"type": "file_suggestions", "query": file_path, "matches": matches[:8]},
                    )
                else:
                    msg = f"❌ '{file_path}' not found in {owner}/{repo}. Try a different name or use `Tell me about the repo` to see top-level files."
                    return msg, {"type": "empty", "message": msg}

            if d["kind"] == "directory":
                files = d["files"]
                return (
                    f"{len(files)} item(s) in {file_path}/: " + ", ".join(f["name"] for f in files[:5]),
                    {"type": "directory", "path": file_path, "url": d["url"], "files": files},
                )
            else:
                return (
                    f"{d['name']} ({d['size']} bytes)",
                    {"type": "file_content", "path": file_path, "name": d["name"],
                     "size": d["size"], "url": d["url"], "content": d["content"]},
                )

        # ── Repo overview ─────────────────────────────────────────────
        if query_type == "repo_info":
            d = await get_repo_info(owner, repo, github_token)
            summary = d["description"] or d["name"]
            return (
                f"{d['full_name']}: {summary[:80]} ({d['language']}, ⭐{d['stars']})",
                {"type": "repo_info", "item": d},
            )

        # ── Issue detail ──────────────────────────────────────────────
        if query_type == "issue_detail" and issue_number:
            d = await get_issue_detail(owner, repo, int(issue_number), github_token)
            return (
                f"Issue #{d['number']}: {d['title']} — {d['state']}",
                {"type": "issue_detail", "item": d},
            )

        # ── Commit detail ─────────────────────────────────────────────
        if query_type == "commit_detail" and commit_sha:
            d = await get_commit(owner, repo, commit_sha, github_token)
            return (
                f"Commit {d['sha']} by {d['author']}: {d['message'][:80]}",
                {"type": "commit_detail", "item": d},
            )

        # ── PR detail ─────────────────────────────────────────────────
        if pr_number and query_type != "issues":
            d = await get_pr(owner, repo, int(pr_number), github_token)
            status = "merged" if d["merged"] else d["state"]
            return (
                f"PR #{d['number']}: {d['title']} — {status}",
                {"type": "pr_detail", "item": d},
            )

        # ── Issues list ───────────────────────────────────────────────
        if query_type == "issues":
            items = await get_open_issues(owner, repo, github_token)
            if not items:
                return f"No open issues in {owner}/{repo}.", {"type": "empty", "message": f"No open issues in {owner}/{repo}."}
            if modifier == "count":
                return (
                    f"{len(items)} open issue(s) in {owner}/{repo}",
                    {"type": "count", "count": len(items), "label": f"Open issues in {owner}/{repo}"},
                )
            if modifier == "latest":
                items = items[:1]
            return (
                f"{len(items)} open issue(s) in {owner}/{repo}",
                {"type": "issue_list", "repo": f"{owner}/{repo}", "items": items},
            )

        # ── Commits list ──────────────────────────────────────────────
        if query_type == "commits":
            items = await get_recent_commits(owner, repo, github_token)
            if not items:
                return "No commits found.", {"type": "empty", "message": "No recent commits found."}
            if modifier == "count":
                return (
                    f"{len(items)} recent commit(s) in {owner}/{repo}",
                    {"type": "count", "count": len(items), "label": f"Recent commits in {owner}/{repo}"},
                )
            if modifier == "latest":
                items = items[:1]
            return (
                f"{len(items)} recent commit(s) in {owner}/{repo}",
                {"type": "commit_list", "repo": f"{owner}/{repo}", "items": items},
            )

        # ── Default: open PRs ─────────────────────────────────────────
        items = await get_open_prs(owner, repo, github_token)
        if not items:
            return f"No open PRs in {owner}/{repo}.", {"type": "empty", "message": f"No open PRs in {owner}/{repo}."}
        if modifier == "count":
            return (
                f"{len(items)} open PR(s) in {owner}/{repo}",
                {"type": "count", "count": len(items), "label": f"Open PRs in {owner}/{repo}"},
            )
        if modifier == "latest":
            items = items[:1]
        return (
            f"{len(items)} open PR(s) in {owner}/{repo}",
            {"type": "pr_list", "repo": f"{owner}/{repo}", "items": items},
        )

    except Exception as e:
        logger.error(f"[status_agent] error: {e}")
        return f"Failed to fetch repo data: {e}", {"type": "error", "message": str(e)}
