from fastapi import APIRouter, status, Response, Path, Depends
from ..models import (
    UserCreate,
    UserResponse,
    UserUpdate,
    User,
)
from ..exceptions import APIException
from ..dependencies import get_current_user
from ..permissions import (
    Permission,
    require_permission,
    require_any_permission,
    PermissionChecker,
)
from ..utils import build_user_response
import src.db as db

router = APIRouter(prefix="/users", tags=["users"])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=UserResponse)
@require_any_permission(Permission.USERS_CREATE)
def create_user(
    new_user: UserCreate, current_user: User = Depends(get_current_user)
):  # Use the Pydantic User model
    if not ((apartment := new_user.apartment) and apartment.number):
        raise APIException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing apartment or apartment number",
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

    # Check apartment access for apartment admins
    if (
        current_user.role == "apartment_admin"
        and apartment.id != current_user.apartment.id
    ):
        raise APIException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only create users for your own apartment",
        )

    if new_user.email:
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
@require_any_permission(Permission.USERS_LIST_ALL, Permission.USERS_LIST_APARTMENT)
def list_users(current_user: User = Depends(get_current_user)):
    if PermissionChecker.has_permission(current_user, Permission.USERS_LIST_ALL):
        users = db.get_all_users()
    elif PermissionChecker.has_permission(
        current_user, Permission.USERS_LIST_APARTMENT
    ):
        users = db.get_apartment_users(current_user.apartment.id)
    else:
        raise APIException(status_code=403, detail="Insufficient permissions")

    return [build_user_response(user) for user in users]


@router.get("/{user_id}", status_code=status.HTTP_200_OK, response_model=UserResponse)
@require_any_permission(Permission.USERS_VIEW_OTHER, Permission.USERS_VIEW_OWN)
def get_user(user_id: int, current_user: User = Depends(get_current_user)):
    user = db.get_user(user_id)
    if not user:
        raise APIException(status_code=404, detail="User not found")

    # Check resource access
    if not PermissionChecker.can_access_user_resource(current_user, user_id, user):
        raise APIException(status_code=403, detail="Cannot access this user")

    return UserResponse(
        id=user.id,
        name=user.name,
        email=user.email,
        role=user.role,
        apartment_number=user.apartment.number,
    )


@router.put("/{user_id}", status_code=status.HTTP_200_OK, response_model=UserResponse)
@require_any_permission(Permission.USERS_UPDATE_OTHER, Permission.USERS_UPDATE_OWN)
def update_user(
    user_id: int,
    updated_user: UserUpdate,
    current_user: User = Depends(get_current_user),
):
    user_to_update = db.get_user(user_id)
    if not user_to_update:
        raise APIException(status_code=404, detail="User not found")

    # Check resource access
    if not PermissionChecker.can_access_user_resource(
        current_user, user_id, user_to_update
    ):
        raise APIException(status_code=403, detail="Cannot access this user")

    # Additional role-specific checks for apartment admins
    if current_user.role == "apartment_admin":
        # Check if trying to set role to admin
        if updated_user.role == "admin":
            raise APIException(
                status_code=403, detail="Only admins can promote users to admin role"
            )
        # Check if trying to update an admin
        if user_to_update.role == "admin":
            raise APIException(
                status_code=403, detail="Apartment admins cannot modify admin users"
            )
        # Check if trying to change apartment
        if (
            updated_user.apartment
            and updated_user.apartment.number != user_to_update.apartment.number
        ):
            raise APIException(
                status_code=403, detail="Only admins can move users between apartments"
            )

    try:
        updated_user_to_return = db.update_user(
            user_id, updated_user.dict(exclude_unset=True)
        )
        if not updated_user_to_return:
            raise APIException(status_code=404, detail="User not found")

        return build_user_response(updated_user_to_return)
    except ValueError as e:
        raise APIException(status_code=400, detail=str(e))


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
@require_permission(Permission.USERS_DELETE_OTHER)
def delete_user(user_id: int, current_user: User = Depends(get_current_user)):
    user_to_delete = db.get_user(user_id)
    if not user_to_delete:
        raise APIException(status_code=404, detail="User not found")

    # Check resource access
    if not PermissionChecker.can_access_user_resource(
        current_user, user_id, user_to_delete
    ):
        raise APIException(status_code=403, detail="Cannot access this user")

    # Additional role-specific checks for apartment admins
    if current_user.role == "apartment_admin":
        if user_to_delete.role == "admin":
            raise APIException(
                status_code=403, detail="Apartment admins cannot delete admin users"
            )

    if db.remove_user(user_id):
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    raise APIException(status_code=500, detail="Failed to delete user")


@router.get("/{user_id}/rfids", status_code=status.HTTP_200_OK)
@require_any_permission(
    Permission.RFIDS_LIST_ALL,
    Permission.RFIDS_LIST_APARTMENT,
    Permission.RFIDS_VIEW_OWN,
)
def list_user_rfids(
    current_user: User = Depends(get_current_user),
    user_id: int = Path(..., description="The ID of the user whose RFIDs to list"),
):
    target_user = db.get_user(user_id)
    if not target_user:
        raise APIException(status_code=404, detail="User not found")

    # Check resource access
    if not PermissionChecker.can_access_user_resource(
        current_user, user_id, target_user
    ):
        raise APIException(status_code=403, detail="Cannot access this user's RFIDs")

    rfids = db.get_user_rfids(user_id)
    return rfids


@router.get("/{user_id}/pins", status_code=status.HTTP_200_OK)
@require_any_permission(
    Permission.PINS_LIST_ALL, Permission.PINS_LIST_APARTMENT, Permission.PINS_VIEW_OWN
)
def list_user_pins(
    current_user: User = Depends(get_current_user),
    user_id: int = Path(..., description="User ID to fetch pins for"),
):
    target_user = db.get_user(user_id)
    if not target_user:
        raise APIException(status_code=404, detail="User not found")

    # Check resource access
    if not PermissionChecker.can_access_user_resource(
        current_user, user_id, target_user
    ):
        raise APIException(status_code=403, detail="Cannot access this user's PINs")

    pins = db.get_user_pins(user_id)
    return pins
