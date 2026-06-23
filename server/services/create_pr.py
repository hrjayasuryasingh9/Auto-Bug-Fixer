from __future__ import annotations

import os
import time
from server.utils.shell import run_cmd
from server.utils.github import create_github_pr
from server.utils.logger import logger


class NoChangesError(RuntimeError):
    """Raised when there's nothing to commit (proposed changes were a no-op)."""


async def open_pr(
    repo_path: str,
    branch_name: str,
    commit_message: str,
    title: str,
    body: str,
    owner: str,
    repo: str,
    token: str,
    base: str = "main",
    paths: list[str] | None = None,
) -> tuple[str, str]:
    """Reusable: branch → stage → commit → push → open a draft PR. Returns
    (pr_url, branch_name).

    `paths` — if given, ONLY these files are staged (so build artifacts / graph
    output left in the working tree never leak into the PR). Falls back to staging
    everything when omitted. Raises NoChangesError if nothing was actually staged.
    """
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}

    logger.info(f"[PR] Creating branch {branch_name} (base {base})")
    await run_cmd(["git", "checkout", "-b", branch_name], cwd=repo_path, env=env)

    if paths:
        await run_cmd(["git", "add", "--", *paths], cwd=repo_path, env=env)
    else:
        await run_cmd(["git", "add", "-A"], cwd=repo_path, env=env)

    staged = await run_cmd(["git", "diff", "--cached", "--name-only"], cwd=repo_path, env=env)
    if not staged.strip():
        raise NoChangesError("No changes to commit")
    logger.info(f"[PR] Staged files:\n{staged.strip()}")

    await run_cmd(["git", "commit", "-m", commit_message], cwd=repo_path, env=env)
    push_url = f"https://x-access-token:{token}@github.com/{owner}/{repo}.git"
    logger.info(f"[PR] Pushing {branch_name}")
    await run_cmd(["git", "push", push_url, branch_name], cwd=repo_path, env=env)

    pr_url = await create_github_pr(
        owner=owner, repo=repo, branch_name=branch_name, error_message="",
        token=token, base=base, title=title, body=body,
    )
    return pr_url, branch_name


async def create_pull_request(
    repo_path: str,
    error_message: str,
    github_token: str,
    github_owner: str,
    github_repo: str,
) -> tuple[str, str]:
    branch_name = f"ai-fix-{int(time.time())}"
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}

    logger.info(f"[PR] Creating branch: {branch_name}")
    await run_cmd(["git", "checkout", "-b", branch_name], cwd=repo_path, env=env)

    logger.info("[PR] Staging changes")
    await run_cmd(["git", "add", "."], cwd=repo_path, env=env)

    logger.info("[PR] Committing fix")
    await run_cmd(
        ["git", "commit", "-m", "fix: automated AI generated fix"],
        cwd=repo_path,
        env=env,
    )

    # GitHub HTTPS auth: x-access-token as username, token as password
    push_url = f"https://x-access-token:{github_token}@github.com/{github_owner}/{github_repo}.git"
    logger.info(f"[PR] Pushing branch {branch_name} to origin")
    await run_cmd(["git", "push", push_url, branch_name], cwd=repo_path, env=env)

    logger.info("[PR] Opening GitHub pull request")
    pr_url = await create_github_pr(
        owner=github_owner,
        repo=github_repo,
        branch_name=branch_name,
        error_message=error_message,
        token=github_token,
    )

    return pr_url, branch_name
