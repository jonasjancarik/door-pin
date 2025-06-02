from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
import os
from src.api.dependencies import get_current_user
from src.api.permissions import Permission, require_permission
from src.db import User  # Assuming User model is in src.db
from src.logger import logger  # For logging access attempts

router = APIRouter()

LOG_FILE_PATH = os.path.join(
    "logs", "app.log"
)  # Path to the log file relative to project root


@router.get("/logs", tags=["logs"], response_class=PlainTextResponse)
@require_permission(Permission.LOGS_VIEW)
async def get_application_logs(current_user: User = Depends(get_current_user)):
    """
    Retrieves the application log file.
    Requires admin privileges.
    """
    logger.info(
        f"Admin user {current_user.id} ({current_user.name}) accessed application logs."
    )
    try:
        if not os.path.exists(LOG_FILE_PATH):
            logger.error(f"Log file not found at {LOG_FILE_PATH}")
            raise HTTPException(status_code=404, detail="Log file not found.")

        with open(LOG_FILE_PATH, "r") as f:
            log_content = f.read()
        return log_content
    except Exception as e:
        logger.error(f"Error reading log file: {e}")
        raise HTTPException(status_code=500, detail="Could not read log file.")
