import os
import stat
import shutil
from server.utils.shell import run_cmd
from server.utils.logger import logger


def _force_rmtree(path: str) -> None:
    """Windows-safe recursive delete — clears read-only flags set by git."""
    def _on_error(func, fpath, _exc_info):
        try:
            os.chmod(fpath, stat.S_IWRITE)
            func(fpath)
        except Exception as e:
            logger.warning(f"[clone] Could not remove {fpath}: {e}")
    shutil.rmtree(path, onerror=_on_error)


async def clone_repo(repo_url: str, repo_name: str, github_token: str = "") -> str:
    dest = os.path.join("server", "temp_repos", repo_name)
    git_dir = os.path.join(dest, ".git")

    # GitHub HTTPS auth
    auth_url = repo_url
    if github_token and repo_url.startswith("https://github.com"):
        auth_url = repo_url.replace("https://", f"https://x-access-token:{github_token}@")

    # Try to update a valid existing clone
    if os.path.exists(git_dir):
        logger.info(f"[clone] Repo cached at {dest} — updating")
        try:
            await run_cmd(["git", "fetch", "--all"], cwd=dest)
            await run_cmd(["git", "reset", "--hard", "origin/HEAD"], cwd=dest)
            logger.info("[clone] Update complete")
            return dest
        except Exception as e:
            logger.warning(f"[clone] Update failed ({e}) — wiping and re-cloning")
            _force_rmtree(dest)

    # Wipe any leftover partial/corrupt directory
    if os.path.exists(dest):
        logger.warning(f"[clone] Stale directory at {dest} — removing")
        _force_rmtree(dest)
        if os.path.exists(dest):
            raise RuntimeError(
                f"Cannot remove stale directory: {dest}. "
                "Close any processes using it and retry."
            )

    os.makedirs(os.path.dirname(dest), exist_ok=True)
    logger.info(f"[clone] Cloning into {dest}")
    await run_cmd(["git", "clone", auth_url, dest], cwd=".")
    logger.info("[clone] Clone complete")
    return dest
