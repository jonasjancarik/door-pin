from fastapi import APIRouter, status, Response, Depends
from typing import List
import secrets
import hashlib
from src.api.models import APIKeyCreate, APIKeyResponse, APIKeyWithSecret
from src.api.dependencies import get_current_user
from src.api.exceptions import APIException
from src.api.permissions import Permission, require_any_permission, PermissionChecker
import src.db as db

router = APIRouter(prefix="/api-keys", tags=["API Keys"])


def generate_api_key() -> tuple[str, str, str]:
    """Generate a new API key, its suffix, and hash."""
    api_key = secrets.token_urlsafe(32)
    suffix = api_key[-4:]
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    return api_key, suffix, key_hash


@router.post("", response_model=APIKeyWithSecret)
@require_any_permission(
    Permission.API_KEYS_CREATE_OTHER, Permission.API_KEYS_CREATE_OWN
)
async def create_api_key(
    data: APIKeyCreate,
    current_user: db.User = Depends(get_current_user),
):
    # If a user_id is provided in the request, we're creating a key for another user
    if data.user_id:
        target_user = db.get_user(data.user_id)
        if not target_user:
            raise APIException(status_code=404, detail="User not found")

        # Check if user can create for the target user
        if not PermissionChecker.can_create_for_user(
            current_user, target_user, Permission.API_KEYS_CREATE_OTHER
        ):
            raise APIException(
                status_code=403, detail="Cannot create API key for this user"
            )

        user_id = target_user.id
    else:
        # If no user_id is provided, create API key for the current user
        user_id = current_user.id

    api_key, suffix, key_hash = generate_api_key()

    db_api_key = db.add_api_key(
        suffix=suffix,
        key_hash=key_hash,
        description=data.description,
        user_id=user_id,
    )

    return APIKeyWithSecret(
        key_suffix=suffix,
        description=data.description,
        created_at=db_api_key.created_at.isoformat(),
        is_active=db_api_key.is_active,
        user_id=user_id,
        api_key=api_key,
    )


@router.get("", status_code=status.HTTP_200_OK)
@require_any_permission(
    Permission.API_KEYS_LIST_ALL,
    Permission.API_KEYS_LIST_APARTMENT,
    Permission.API_KEYS_LIST_OWN,
)
def list_api_keys(current_user: db.User = Depends(get_current_user)):
    if PermissionChecker.has_permission(current_user, Permission.API_KEYS_LIST_ALL):
        api_keys = db.get_all_api_keys()
    elif PermissionChecker.has_permission(
        current_user, Permission.API_KEYS_LIST_APARTMENT
    ):
        api_keys = db.get_apartment_api_keys(current_user.apartment_id)
    else:
        # Regular users can only see their own API keys
        api_keys = db.get_user_api_keys(current_user.id)

    return [
        APIKeyResponse(
            key_suffix=api_key.key_suffix,
            description=api_key.description,
            created_at=api_key.created_at.isoformat(),
            is_active=api_key.is_active,
            user_id=api_key.user_id,
        )
        for api_key in api_keys
    ]


@router.delete("/{key_suffix}")
@require_any_permission(
    Permission.API_KEYS_DELETE_OTHER, Permission.API_KEYS_DELETE_OWN
)
async def delete_api_key(
    key_suffix: str,
    current_user: db.User = Depends(get_current_user),
):
    api_key = db.get_api_key(key_suffix)
    if not api_key:
        raise APIException(status_code=404, detail="API key not found")

    # Check resource access
    key_owner = db.get_api_key_owner(api_key.user_id)
    if not PermissionChecker.can_access_user_resource(
        current_user, api_key.user_id, key_owner
    ):
        raise APIException(status_code=403, detail="Cannot access this API key")

    if db.delete_api_key(key_suffix):
        return {"message": "API key deleted"}
    raise APIException(status_code=500, detail="Failed to delete API key")
