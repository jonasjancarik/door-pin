from fastapi import APIRouter, Depends, status
from ..dependencies import authenticate_user
import src.utils as utils
import src.db as db
from src.door_manager import door_manager

router = APIRouter(prefix="/doors", tags=["doors"])


@router.post("/unlock", status_code=status.HTTP_200_OK)
async def unlock_door(_: db.User = Depends(authenticate_user)):
    return await door_manager.unlock(utils.unlock_door, utils.RELAY_ACTIVATION_TIME)
