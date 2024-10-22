from fastapi import APIRouter, Depends, status
from ..dependencies import authenticate_user
import src.utils as utils
import asyncio
import src.db as db

router = APIRouter(prefix="/doors", tags=["doors"])


@router.post("/unlock", status_code=status.HTTP_200_OK)
async def unlock_door(_: db.User = Depends(authenticate_user)):
    asyncio.create_task(utils.unlock_door())
    return {"message": "Door unlock initiated"}
