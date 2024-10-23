from fastapi import APIRouter, status
from ..exceptions import APIException
from ...reader.reader import start_reader, stop_reader, get_reader_status
from ..models import User

router = APIRouter(prefix="/reader", tags=["reader"])


@router.post("/start", status_code=status.HTTP_200_OK)
async def start_reader_endpoint(current_user: User):
    if current_user.role != "admin":
        raise APIException(status_code=403, detail="Admin access required")
    if get_reader_status() == "running":
        raise APIException(status_code=400, detail="Reader is already running")
    start_reader()
    return {"message": "Reader started successfully"}


@router.post("/stop", status_code=status.HTTP_200_OK)
async def stop_reader_endpoint(current_user: User):
    if current_user.role != "admin":
        raise APIException(status_code=403, detail="Admin access required")
    if get_reader_status() == "stopped":
        raise APIException(status_code=400, detail="Reader is not running")
    stop_reader()
    return {"message": "Reader stopped successfully"}


@router.get("/status", status_code=status.HTTP_200_OK)
async def get_reader_status_endpoint(
    current_user: User,
):
    if current_user.role != "admin":
        raise APIException(status_code=403, detail="Admin access required")
    return {"status": get_reader_status()}
