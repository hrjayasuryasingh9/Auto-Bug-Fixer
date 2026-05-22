import aiofiles
from server.utils.logger import logger


async def apply_patch(file_path: str, updated_code: str) -> None:
    logger.info(f"[patch] Writing fix to {file_path}")
    try:
        async with aiofiles.open(file_path, "w", encoding="utf-8") as f:
            await f.write(updated_code)
    except OSError as e:
        raise RuntimeError(f"Failed to write fix to {file_path}: {e}") from e
