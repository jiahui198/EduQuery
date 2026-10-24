from datetime import datetime

from fastapi import APIRouter

from eduquery.core.config import settings

router = APIRouter()

@router.get("/health",summary="健康检查")
async def health()->dict:
    return{
        "app":settings.APP_NAME,
        "env":settings.APP_ENV,
        "status":"ok",
        "server_time":datetime.now().isoformat(timespec="seconds")
    }
