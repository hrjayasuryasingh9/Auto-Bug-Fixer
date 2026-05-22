import os
import time
from server.utils.shell import run_cmd
from server.utils.github import create_github_pr
from server.utils.logger import logger


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
