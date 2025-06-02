from fastapi import APIRouter, status, Response, Depends
from ..models import PINCreate, PINResponse, PINUpdate, User
from ..exceptions import APIException
from ..dependencies import get_current_user
from ..permissions import Permission, require_any_permission, PermissionChecker
import src.db as db
import src.utils as utils
import random
import os
import dotenv

dotenv.load_dotenv()

router = APIRouter(prefix="/pins", tags=["pins"])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=PINResponse)
@require_any_permission(Permission.PINS_CREATE_OTHER, Permission.PINS_CREATE_OWN)
def create_pin(pin_request: PINCreate, current_user: User = Depends(get_current_user)):
    if pin_request.user_id:
        target_user = db.get_user(pin_request.user_id)
        if not target_user:
            raise APIException(status_code=404, detail="User not found")

        # Check if user can create for the target user
        if not PermissionChecker.can_create_for_user(
            current_user, target_user, Permission.PINS_CREATE_OTHER
        ):
            raise APIException(
                status_code=403, detail="Cannot create PIN for this user"
            )

        user_id = target_user.id
    else:
        # If no user_id is provided, create PIN for the current user
        user_id = current_user.id
        target_user = current_user

    # For guest users, generate a random PIN if none provided
    if target_user.role == "guest":
        if pin_request.pin:
            raise APIException(
                status_code=400,
                detail="PINs for guests must be automatically generated",
            )

        # Generate a random unique PIN
        while True:
            pin = "".join(
                random.choices("0123456789", k=int(os.getenv("PIN_LENGTH", 4)))
            )
            # Check for uniqueness
            all_pins = db.get_all_pins()
            is_unique = True
            for existing_pin in all_pins:
                if utils.hash_secret(pin, existing_pin.salt) == existing_pin.hashed_pin:
                    is_unique = False
                    break
            if is_unique:
                break
    else:
        # For non-guest users (including regular users), PIN must be provided
        if not pin_request.pin:
            raise APIException(
                status_code=400,
                detail="PIN must be provided for non-guest users",
            )
        pin = pin_request.pin

    salt = utils.generate_salt()
    hashed_pin = utils.hash_secret(payload=pin, salt=salt)

    saved_pin = db.save_pin(user_id, hashed_pin, pin_request.label, salt)

    response = PINResponse(
        id=saved_pin.id,
        label=saved_pin.label,
        created_at=str(saved_pin.created_at),
        user_id=user_id,
        user_email=target_user.email,
    )

    # Only include the PIN in the response if it's a guest user
    if target_user.role == "guest":
        response.pin = pin

    return response


@router.patch("/{pin_id}", status_code=status.HTTP_200_OK)
@require_any_permission(Permission.PINS_UPDATE_OTHER, Permission.PINS_UPDATE_OWN)
def update_pin(
    pin_id: int, pin_request: PINUpdate, current_user: User = Depends(get_current_user)
):
    pin = db.get_pin(pin_id)
    if not pin:
        raise APIException(status_code=404, detail="PIN not found")

    # Check resource access
    if not PermissionChecker.can_access_user_resource(
        current_user, pin.user_id, pin.user
    ):
        raise APIException(status_code=403, detail="Cannot access this PIN")

    salt = utils.generate_salt()
    hashed_pin = (
        utils.hash_secret(payload=pin_request.pin, salt=salt)
        if pin_request.pin
        else None
    )
    updated_pin = db.update_pin(pin_id, hashed_pin, pin_request.label, salt)
    if updated_pin:
        return {"status": "PIN updated", "pin_id": updated_pin.id}
    raise APIException(status_code=500, detail="Failed to update PIN")


@router.delete("/{pin_id}", status_code=status.HTTP_204_NO_CONTENT)
@require_any_permission(Permission.PINS_DELETE_OTHER, Permission.PINS_DELETE_OWN)
def delete_pin(pin_id: int, current_user: User = Depends(get_current_user)):
    pin = db.get_pin(pin_id)
    if not pin:
        raise APIException(status_code=404, detail="PIN not found")

    # Check resource access
    if not PermissionChecker.can_access_user_resource(
        current_user, pin.user_id, pin.user
    ):
        raise APIException(status_code=403, detail="Cannot access this PIN")

    if db.delete_pin(pin_id):
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    raise APIException(status_code=500, detail="Failed to delete PIN")


@router.get("", status_code=status.HTTP_200_OK, response_model=list[PINResponse])
@require_any_permission(Permission.PINS_LIST_ALL, Permission.PINS_LIST_APARTMENT)
def list_pins(current_user: User = Depends(get_current_user)):
    if PermissionChecker.has_permission(current_user, Permission.PINS_LIST_ALL):
        pins = db.get_all_pins()
    elif PermissionChecker.has_permission(current_user, Permission.PINS_LIST_APARTMENT):
        pins = db.get_apartment_pins(current_user.apartment.id)
    else:
        raise APIException(status_code=403, detail="Insufficient permissions")

    return [
        PINResponse(
            id=pin.id,
            label=pin.label,
            created_at=str(pin.created_at),
            user_id=pin.user_id,
            user_email=pin.user.email,
        )
        for pin in pins
    ]
