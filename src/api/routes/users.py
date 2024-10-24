from fastapi import APIRouter, status, Response, Path, Depends
from ..models import (
    UserCreate,
    UserResponse,
    UserUpdate,
    User,
)
from ..exceptions import APIException
from ..dependencies import get_current_user
from ..utils import build_user_response
import src.db as db

router = APIRouter(prefix="/users", tags=["users"])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=UserResponse)
def create_user(
    new_user: UserCreate, current_user: User = Depends(get_current_user)
):  # Use the Pydantic User model
    if current_user.role == "guest":
        raise APIException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Guests cannot create users"
        )

    if (
        not ((apartment := new_user.apartment) and apartment.number)
        or not new_user.email
    ):
        raise APIException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing apartment, apartment number, or email",
        )

    if new_user.role and new_user.role == "admin" and current_user.role != "admin":
        raise APIException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can create admin users",
        )

    apartment = db.get_apartment_by_number(new_user.apartment.number)
    if not apartment:
        raise APIException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Apartment with number {new_user.apartment.number} not found",
        )

    if apartment.id != current_user.apartment.id and current_user.role != "admin":
        raise APIException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only create users for your own apartment",
        )

    existing_user = db.get_user(new_user.email)
    if existing_user:
        raise APIException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"User with email {new_user.email} already exists",
        )

    created_user = db.add_user(
        {
            "name": new_user.name,
            "email": new_user.email,
            "role": new_user.role,
            "apartment_id": apartment.id,
            "creator_id": current_user.id,
        }
    )

    return build_user_response(created_user)


@router.get("", status_code=status.HTTP_200_OK, response_model=list[UserResponse])
def list_users(current_user: User = Depends(get_current_user)):
    if current_user.role == "admin":
        users = db.get_all_users()
    elif current_user.role == "apartment_admin":
        users = db.get_apartment_users(current_user.apartment.id)
    else:
        raise APIException(status_code=403, detail="Guests cannot list users")

    return [build_user_response(user) for user in users]


@router.get("/{user_id}", status_code=status.HTTP_200_OK, response_model=UserResponse)
def get_user(user_id: int, current_user: User = Depends(get_current_user)):
    user = db.get_user(user_id)
    if not user:
        raise APIException(status_code=404, detail="User not found")

    if current_user.role != "admin" and current_user.id != user_id:
        if current_user.apartment.id != user.apartment.id:
            raise APIException(
                status_code=403, detail="Admin access required to view other users"
            )
        elif current_user.role != "apartment_admin":
            raise APIException(
                status_code=403,
                detail="Only apartment admins (and admins) can view other users from the same apartment.",
            )

    return UserResponse(
        id=user.id,
        name=user.name,
        email=user.email,
        role=user.role,
        apartment_number=user.apartment.number,
    )


@router.put("/{user_id}", status_code=status.HTTP_200_OK, response_model=UserResponse)
def update_user(
    user_id: int,
    updated_user: UserUpdate,
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "admin":
        raise APIException(status_code=403, detail="Admin access required")
    try:
        updated_user_to_return = db.update_user(
            user_id, updated_user.dict(exclude_unset=True)
        )
        if not updated_user_to_return:
            raise APIException(status_code=404, detail="User not found")

        return UserResponse(
            id=updated_user_to_return.id,
            name=updated_user_to_return.name,
            email=updated_user_to_return.email,
            role=updated_user_to_return.role,
            apartment_number=updated_user_to_return.apartment.number,
        )
    except ValueError as e:
        raise APIException(status_code=400, detail=str(e))


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: int, current_user: User = Depends(get_current_user)):
    if current_user.role not in ["admin", "apartment_admin"]:
        raise APIException(status_code=403, detail="Insufficient permissions")

    user_to_delete = db.get_user(user_id)
    if not user_to_delete:
        raise APIException(status_code=404, detail="User not found")

    if current_user.role == "apartment_admin":
        if user_to_delete.apartment_id != current_user.apartment_id:
            raise APIException(
                status_code=403, detail="Cannot delete users from other apartments"
            )
        if user_to_delete.role == "admin":
            raise APIException(
                status_code=403, detail="Apartment admins cannot delete admin users"
            )

    if db.remove_user(user_id):
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    raise APIException(status_code=500, detail="Failed to delete user")


@router.get("/{user_id}/rfids", status_code=status.HTTP_200_OK)
def list_user_rfids(
    current_user: User = Depends(get_current_user),
    user_id: int = Path(..., description="The ID of the user whose RFIDs to list"),
):
    if current_user.role == "admin":
        rfids = db.get_user_rfids(user_id)
    elif (
        current_user.role == "apartment_admin"
        and current_user.apartment_id == db.get_user(user_id).apartment_id
    ):
        rfids = db.get_user_rfids(user_id)
    elif current_user.id == user_id:
        rfids = db.get_user_rfids(user_id)
    else:
        raise APIException(status_code=403, detail="Insufficient permissions")

    return [
        {
            "id": rfid.id,
            "label": rfid.label,
            "created_at": rfid.created_at,
            "last_four_digits": rfid.last_four_digits,
        }
        for rfid in rfids
    ]


@router.get("/{user_id}/pins", status_code=status.HTTP_200_OK)
def list_user_pins(
    current_user: User = Depends(get_current_user),
    user_id: int = Path(..., description="User ID to fetch pins for"),
):
    if current_user.role == "admin":
        pins = db.get_user_pins(user_id)
    elif (
        current_user.role == "apartment_admin"
        and current_user.apartment_id == db.get_user(user_id).apartment_id
    ):
        pins = db.get_user_pins(user_id)
    elif current_user.id == user_id:
        pins = db.get_user_pins(user_id)
    else:
        raise APIException(status_code=403, detail="Insufficient permissions")

    return [
        {
            "id": pin.id,
            "label": pin.label,
            "created_at": pin.created_at,
        }
        for pin in pins
    ]
