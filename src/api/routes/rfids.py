from fastapi import APIRouter, Depends, status, Response
from ..models import RFIDCreate, RFIDResponse
from ..exceptions import APIException
from ..dependencies import authenticate_user
from ..utils import user_return_format
import src.db as db
import src.utils as utils
import logging
from ...reader.reader import read_single_input

router = APIRouter(prefix="/rfids", tags=["rfids"])


@router.post("", status_code=status.HTTP_201_CREATED)
def create_rfid(
    rfid_request: RFIDCreate, current_user: db.User = Depends(authenticate_user)
):
    salt = utils.generate_salt()
    hashed_uuid = utils.hash_secret(payload=rfid_request.uuid, salt=salt)
    last_four_digits = rfid_request.uuid[-4:]

    if rfid_request.user_id:
        target_user = db.get_user(rfid_request.user_id)
        if not target_user:
            raise APIException(status_code=404, detail="User not found")

        if current_user.role == "admin":
            # Admins can create RFIDs for any user
            user_id = target_user.id
        elif current_user.role == "apartment_admin":
            # Apartment admins can only create RFIDs for users in their apartment
            if target_user.apartment_id != current_user.apartment_id:
                raise APIException(
                    status_code=403,
                    detail="Cannot create RFIDs for users from other apartments",
                )
            user_id = target_user.id
        else:
            raise APIException(
                status_code=403,
                detail="Insufficient permissions to create RFIDs for other users",
            )
    else:
        # If no user_id is provided, create RFID for the current user
        user_id = current_user.id

    rfid = db.save_rfid(
        user_id, hashed_uuid, salt, last_four_digits, rfid_request.label
    )
    return {
        "status": "RFID created",
        "rfid": {
            "id": rfid.id,
            "label": rfid.label,
            "user_id": user_id,
            "last_four_digits": last_four_digits,
        },
    }


@router.get("/read", status_code=status.HTTP_200_OK)
async def read_rfid(timeout: int, user: db.User = Depends(authenticate_user)):
    logging.info(f"Attempting to read RFID with timeout: {timeout}")
    try:
        rfid_uuid = await read_single_input(timeout=min(timeout, 30))
        if not rfid_uuid:
            logging.warning("RFID not found within the timeout period")
            raise APIException(status_code=404, detail="RFID not found")
        logging.info(f"Successfully read RFID: {rfid_uuid}")
        return {"uuid": rfid_uuid}
    except Exception as e:
        logging.error(f"Error reading RFID: {str(e)}")
        raise APIException(status_code=500, detail=f"Error reading RFID: {str(e)}")


@router.delete("/{rfid_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_rfid(rfid_id: int, current_user: db.User = Depends(authenticate_user)):
    rfid = db.get_rfid(rfid_id)
    if not rfid:
        raise APIException(status_code=404, detail="RFID not found")

    if current_user.role == "admin":
        # Admins can delete any RFID
        pass
    elif current_user.role == "apartment_admin":
        # Apartment admins can only delete RFIDs from their apartment
        if rfid.user.apartment_id != current_user.apartment_id:
            raise APIException(
                status_code=403,
                detail="Cannot delete RFIDs for users from other apartments",
            )
    elif current_user.role == "guest":
        # Guests can only delete their own RFIDs
        if rfid.user_id != current_user.id:
            raise APIException(
                status_code=403, detail="Guests can only delete their own RFIDs"
            )
    else:
        raise APIException(status_code=403, detail="Insufficient permissions")

    if db.delete_rfid(rfid_id):
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    raise APIException(status_code=500, detail="Failed to delete RFID")


@router.get("", status_code=status.HTTP_200_OK)
def list_rfids(current_user: db.User = Depends(authenticate_user)):
    if current_user.role == "admin":
        rfids = db.get_all_rfids()
    elif current_user.role == "apartment_admin":
        rfids = db.get_apartment_rfids(current_user.apartment.id)
    else:
        raise APIException(status_code=403, detail="Guests cannot list RFIDs")

    return [
        {
            "id": rfid.id,
            "label": rfid.label,
            "created_at": rfid.created_at,
            "user_id": rfid.user_id,
            "user_email": rfid.user.email,
            "last_four_digits": rfid.last_four_digits,
        }
        for rfid in rfids
    ]
