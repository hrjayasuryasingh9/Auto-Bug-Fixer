"""Explicit `!` commands — handled deterministically (no LLM classification).

Returns a ready-to-send plain-text reply, or None if the text is not a command
we own (so the caller falls through to normal intent handling).

Formatting uses `*bold*` + unicode emoji, which render on both Slack and WhatsApp.
"""
from __future__ import annotations

from server.adapters.github_adapter import list_user_repos, repo_exists
from server.services.context_store import (
    get_active_repo, set_active_repo, get_technical, set_mode,
)
from server.utils.credentials import github_token, github_owner, github_repo

HELP_TEXT = (
    "*AI Engineering Assistant* 🤖\n\n"
    "*Repo commands*\n"
    "  !repos             — list repos this bot can access\n"
    "  !repo owner/name   — set the active repo for this chat\n"
    "  !repo name         — set repo (keeps current owner)\n"
    "  !status            — show the active repo & answer style\n\n"
    "*Answer style*\n"
    "  !technical         — developer detail (file & function names)\n"
    "  !simple            — plain English (no code details)\n\n"
    "  !help              — this message\n\n"
    "*Just ask naturally*\n"
    "  What PRs are open?\n"
    "  Show recent commits\n"
    "  List open issues\n"
    "  How does the error fix pipeline work?\n"
    "  Tell me about the server folder"
)


def is_command(text: str) -> bool:
    return text.strip().startswith("!")


async def resolve_and_set_repo(ctx: dict, owner: str, repo: str) -> str:
    """Validate + persist the active repo for this context. Shared by the !repo
    command and the natural-language repo_switch intent.

    When no owner is given, resolves it: tries the current/default owner, then
    looks the repo name up among the repos the token can access.
    """
    repo = (repo or "").strip().strip("/")
    owner = (owner or "").strip()
    if not repo:
        return "❌ Tell me which repo — e.g. *owner/name*, or “switch to owner/name”."

    token = github_token()
    if not token:
        return "⚠️ No GITHUB_TOKEN configured on the server (.env)."

    if not owner:
        # 1) current context owner, then env default — use if it actually has the repo
        active = get_active_repo(ctx)
        candidate = (active or {}).get("owner") or github_owner()
        if candidate and await repo_exists(candidate, repo, token):
            owner = candidate
        else:
            # 2) search accessible repos by name (case-insensitive)
            try:
                repos = await list_user_repos(token)
            except Exception:
                repos = []
            matches = [r for r in repos if r["name"].lower() == repo.lower()]
            if len(matches) == 1:
                owner, repo = matches[0]["owner"], matches[0]["name"]
            elif len(matches) > 1:
                opts = ", ".join(f"{m['owner']}/{m['name']}" for m in matches)
                return f"Found multiple repos named *{repo}*: {opts}\nUse owner/name to pick one."
            else:
                return (f"❌ Couldn't find a repo named *{repo}* you can access.\n"
                        f"Run !repos to see the list, then use owner/name.")

    if not await repo_exists(owner, repo, token):
        return (f"❌ Can't access *{owner}/{repo}*. Check the name, "
                f"or run !repos to see what's available.")
    set_active_repo(ctx, owner, repo)
    return f"✅ Your active repo is now *{owner}/{repo}*. Ask away!"


async def handle_command(text: str, ctx: dict) -> str | None:
    text = (text or "").strip()
    if not text.startswith("!"):
        return None

    parts = text[1:].strip().split()
    cmd = parts[0].lower() if parts else ""
    arg = " ".join(parts[1:]).strip()

    if cmd == "help":
        return HELP_TEXT

    if cmd in ("technical", "tech"):
        set_mode(ctx, True)
        return ("🔧 *Technical mode ON* — answers will include file names, functions, "
                "and code details.\nSend !simple to switch back.")

    if cmd in ("simple", "plain"):
        set_mode(ctx, False)
        return ("💬 *Simple mode ON* — answers will use plain language, no code details.\n"
                "Send !technical for developer detail.")

    if cmd in ("status", "whoami"):
        mode = "🔧 Technical" if get_technical(ctx) else "💬 Simple"
        active = get_active_repo(ctx)
        if active and active.get("owner") and active.get("repo"):
            return (f"📂 Your active repo: *{active['owner']}/{active['repo']}*\n"
                    f"🗣️ Answer style: {mode}")
        d_owner, d_repo = github_owner(), github_repo()
        if d_owner and d_repo:
            return (f"📂 Using the server default repo: *{d_owner}/{d_repo}*\n"
                    f"🗣️ Answer style: {mode}\n"
                    f"Switch repo with !repo owner/name")
        return f"⚠️ No repo connected. Use !repos, then !repo owner/name.\n🗣️ Answer style: {mode}"

    if cmd == "repos":
        token = github_token()
        if not token:
            return "⚠️ No GITHUB_TOKEN configured on the server (.env)."
        try:
            repos = await list_user_repos(token)
        except Exception as e:
            return f"❌ Could not list repos: {e}"
        if not repos:
            return "No repos found for the configured token."
        shown = repos[:50]
        lines = [f"*Repos this bot can access ({len(repos)}):*", ""]
        for r in shown:
            lines.append(f"  {'🔒' if r['private'] else '🌐'} {r['full_name']}")
        if len(repos) > len(shown):
            lines.append(f"  …and {len(repos) - len(shown)} more")
        lines.append("")
        lines.append("Switch with !repo owner/name")
        return "\n".join(lines)

    if cmd == "repo":
        if not arg:
            active = get_active_repo(ctx)
            if active and active.get("owner") and active.get("repo"):
                return (f"Your active repo: *{active['owner']}/{active['repo']}*\n"
                        f"Use !repo owner/name to switch, or !repos to list.")
            return "No active repo. Use !repo owner/name to set one, or !repos to list."

        if "/" in arg:
            owner, _, repo = arg.partition("/")
        else:
            owner, repo = "", arg
        return await resolve_and_set_repo(ctx, owner, repo)

    return None  # unknown ! command → fall through to normal handling
