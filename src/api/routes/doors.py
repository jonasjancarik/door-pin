from fastapi import APIRouter, status
import src.utils as utils
from ..models import User
from src.door_manager import door_manager

router = APIRouter(prefix="/doors", tags=["doors"])


@router.post("/unlock", status_code=status.HTTP_200_OK)
async def unlock_door(_: User):
    return await door_manager.unlock(utils.unlock_door, utils.RELAY_ACTIVATION_TIME)
