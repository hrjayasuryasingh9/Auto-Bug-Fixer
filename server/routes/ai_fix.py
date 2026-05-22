import traceback
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from server.models.schemas import ErrorReport, FixResponse
from server.services.analyze_error import process_error
from server.utils.logger import logger

router = APIRouter()


@router.post("/")
async def handle_error(error: ErrorReport):
    logger.info(f"[request] POST /api/ai-fix/ — {error.message[:120]}")
    try:
        result = await process_error(error)
        return JSONResponse(
            status_code=200,
            content=FixResponse(success=True, **result).model_dump(),
        )
    except Exception as e:
        err_text = str(e) or repr(e) or "unknown error"
        logger.error(f"[request] Pipeline failed: {err_text}")
        logger.error(traceback.format_exc())
        return JSONResponse(
            status_code=500,
            content=FixResponse(success=False, error=err_text).model_dump(),
        )
