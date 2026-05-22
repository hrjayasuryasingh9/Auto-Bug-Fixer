from server.utils.shell import run_shell
from server.utils.logger import logger


async def validate_fix(repo_path: str) -> bool:
    logger.info(f"[validate] Running checks at {repo_path}")

    install_ok = await run_shell("npm install", repo_path)
    if not install_ok:
        logger.warning("[validate] npm install failed — skipping build and lint")
        return False

    build_ok = await run_shell("npm run build", repo_path)
    lint_ok = await run_shell("npm run lint", repo_path)

    passed = build_ok and lint_ok
    if passed:
        logger.info("[validate] All checks passed")
    else:
        logger.warning("[validate] Some checks failed — PR will be opened as draft for human review")
    return passed
