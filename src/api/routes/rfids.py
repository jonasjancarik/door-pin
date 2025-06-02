from fastapi import APIRouter, status, Response, Depends
from ..models import RFIDCreate, RFIDResponse, User
from ..exceptions import APIException
from ..utils import build_user_response
from ..dependencies import get_current_user
from ..permissions import Permission, require_any_permission, PermissionChecker
import src.db as db
import src.utils as utils
from src.logger import logger
from ...reader.reader import (
    read_single_input,
    start_reader,
    stop_reader,
    get_reader_status,
)


router = APIRouter(prefix="/rfids", tags=["rfids"])


@router.post("", status_code=status.HTTP_201_CREATED)
@require_any_permission(Permission.RFIDS_CREATE_OTHER, Permission.RFIDS_CREATE_OWN)
def create_rfid(
    rfid_request: RFIDCreate, current_user: User = Depends(get_current_user)
):
    salt = utils.generate_salt()
    hashed_uuid = utils.hash_secret(payload=rfid_request.uuid, salt=salt)
    last_four_digits = rfid_request.uuid[-4:]

    if rfid_request.user_id:
        target_user = db.get_user(rfid_request.user_id)
        if not target_user:
            raise APIException(status_code=404, detail="User not found")

        # Check if user can create for the target user
        if not PermissionChecker.can_create_for_user(
            current_user, target_user, Permission.RFIDS_CREATE_OTHER
        ):
            raise APIException(
                status_code=403, detail="Cannot create RFID for this user"
            )

        user_id = target_user.id
    else:
        # If no user_id is provided, create RFID for the current user
        user_id = current_user.id
        target_user = current_user

    rfid = db.save_rfid(
        user_id, hashed_uuid, salt, last_four_digits, rfid_request.label
    )
    return {
        "status": "RFID created",
        "rfid": RFIDResponse(
            id=rfid.id,
            label=rfid.label,
            created_at=str(rfid.created_at),
            user_id=user_id,
            user_email=target_user.email,
            last_four_digits=last_four_digits,
        ),
        "user": build_user_response(target_user),
    }


@router.get("/read", status_code=status.HTTP_200_OK)
async def read_rfid(timeout: int, user: User = Depends(get_current_user)):
    logger.info(f"Attempting to read RFID with timeout: {timeout}")
    try:
        # stop reader if it's running
        if get_reader_status() == "running":
            logger.info("Stopping reader before reading RFID")
            stop_reader()
        rfid_uuid = await read_single_input(timeout=min(timeout, 30))
        if not rfid_uuid:
            logger.warning("No RFID scanned within timeout period")
            return APIException(
                status_code=404, detail="No RFID scanned within timeout period"
            )
        logger.info(f"Successfully read RFID: {rfid_uuid}")
        # start reader if it was stopped
        if get_reader_status() == "stopped":
            logger.info("Starting reader after reading RFID")
            start_reader()
        return {"uuid": rfid_uuid}
    except Exception as e:
        logger.error(f"Error reading RFID: {str(e)}")
        raise APIException(status_code=500, detail=f"Error reading RFID: {str(e)}")


@router.delete("/{rfid_id}", status_code=status.HTTP_204_NO_CONTENT)
@require_any_permission(Permission.RFIDS_DELETE_OTHER, Permission.RFIDS_DELETE_OWN)
def delete_rfid(rfid_id: int, current_user: User = Depends(get_current_user)):
    rfid = db.get_rfid(rfid_id)
    if not rfid:
        raise APIException(status_code=404, detail="RFID not found")

    # Check resource access
    if not PermissionChecker.can_access_user_resource(
        current_user, rfid.user_id, rfid.user
    ):
        raise APIException(status_code=403, detail="Cannot access this RFID")

    if db.delete_rfid(rfid_id):
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    raise APIException(status_code=500, detail="Failed to delete RFID")


@router.get("", status_code=status.HTTP_200_OK)
@require_any_permission(Permission.RFIDS_LIST_ALL, Permission.RFIDS_LIST_APARTMENT)
def list_rfids(current_user: User = Depends(get_current_user)):
    if PermissionChecker.has_permission(current_user, Permission.RFIDS_LIST_ALL):
        rfids = db.get_all_rfids()
    elif PermissionChecker.has_permission(
        current_user, Permission.RFIDS_LIST_APARTMENT
    ):
        rfids = db.get_apartment_rfids(current_user.apartment.id)
    else:
        raise APIException(status_code=403, detail="Insufficient permissions")

    return [
        RFIDResponse(
            id=rfid.id,
            label=rfid.label,
            created_at=str(rfid.created_at),
            user_id=rfid.user_id,
            user_email=rfid.user.email,
            last_four_digits=rfid.last_four_digits,
        )
        for rfid in rfids
    ]
