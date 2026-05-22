import os
import traceback
from server.models.schemas import ErrorReport
from server.services.clone_repo import clone_repo
from server.services.generate_fix import generate_fix
from server.services.apply_patch import apply_patch
from server.services.validate_fix import validate_fix
from server.services.create_pr import create_pull_request
from server.utils.logger import logger


async def process_error(error: ErrorReport) -> dict:
    logger.info("=" * 60)
    logger.info(f"[pipeline] Error: {error.message}")
    logger.info(f"[pipeline] Repo:  {error.repo_url}")
    logger.info(f"[pipeline] File:  {error.target_file}")
    if error.line_number is not None:
        logger.info(f"[pipeline] Location: line {error.line_number}, col {error.column_number}")
    logger.info("=" * 60)

    try:
        # Step 1
        logger.info("[step 1/6] Cloning / updating repository")
        repo_path = await clone_repo(error.repo_url, error.repo_name, error.github_token)

        # Step 2
        logger.info("[step 2/6] Reading target file")
        file_path = os.path.join(repo_path, error.target_file)
        if not os.path.exists(file_path):
            raise FileNotFoundError(
                f"target_file not found in repo: {error.target_file}"
            )
        with open(file_path, "r", encoding="utf-8") as f:
            file_content = f.read()
        logger.info(f"[step 2/6] Read {len(file_content)} chars from {file_path}")

        # Step 3
        logger.info("[step 3/6] Sending to Claude for fix generation")
        error_dict = error.model_dump(exclude_none=True)
        fixed_code = await generate_fix(error_dict, file_content, file_path, error.anthropic_api_key)
        logger.info(f"[step 3/6] Fix received — full file: {len(fixed_code)} chars")

        # Step 4
        logger.info("[step 4/6] Applying fix to file")
        await apply_patch(file_path, fixed_code)

        # Step 5
        logger.info("[step 5/6] Validating fix (npm build + lint)")
        await validate_fix(repo_path)

        # Step 6
        logger.info("[step 6/6] Creating GitHub pull request")
        pr_url, branch_name = await create_pull_request(
            repo_path,
            error.message,
            error.github_token,
            error.github_owner,
            error.github_repo,
        )

        logger.info("=" * 60)
        logger.info(f"[pipeline] Done. PR: {pr_url}")
        logger.info("=" * 60)

        return {
            "pr_url": pr_url,
            "branch_name": branch_name,
            "message": "Fix applied and PR created successfully",
        }

    except Exception as e:
        logger.error("[pipeline] FAILED")
        logger.error(traceback.format_exc())
        raise RuntimeError(str(e) or repr(e)) from e
