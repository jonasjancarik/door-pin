from fastapi import APIRouter, status, Response, Depends
from typing import List
import secrets
import hashlib
from src.api.models import APIKeyCreate, APIKeyResponse, APIKeyWithSecret
from src.api.dependencies import get_current_user
from src.api.exceptions import APIException
import src.db as db

router = APIRouter(prefix="/api-keys", tags=["API Keys"])


def generate_api_key() -> tuple[str, str, str]:
    """Generate a new API key, its suffix, and hash."""
    api_key = secrets.token_urlsafe(32)
    suffix = api_key[-4:]
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    return api_key, suffix, key_hash


@router.post("", response_model=APIKeyWithSecret)
async def create_api_key(
    data: APIKeyCreate,
    current_user: db.User = Depends(get_current_user),
):
    if current_user.role == "guest":
        raise APIException(
            status_code=403,
            detail="Guests cannot create API keys",
        )

    # If a user_id is provided in the request, we're creating a key for another user
    if data.user_id:
        target_user = db.get_user(data.user_id)
        if not target_user:
            raise APIException(status_code=404, detail="User not found")

        if current_user.role == "admin":
            # Admins can create API keys for any user
            user_id = target_user.id
        elif current_user.role == "apartment_admin":
            # Apartment admins can only create API keys for users in their apartment
            if target_user.apartment_id != current_user.apartment_id:
                raise APIException(
                    status_code=403,
                    detail="Cannot create API keys for users from other apartments",
                )
            user_id = target_user.id
        else:
            raise APIException(
                status_code=403,
                detail="Insufficient permissions to create API keys for other users",
            )
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
def list_api_keys(current_user: db.User = Depends(get_current_user)):
    if current_user.role == "admin":
        api_keys = db.get_all_api_keys()
    elif current_user.role == "apartment_admin":
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
async def delete_api_key(
    key_suffix: str,
    current_user: db.User = Depends(get_current_user),
):
    api_key = db.get_api_key(key_suffix)
    if not api_key:
        raise APIException(status_code=404, detail="API key not found")

    if current_user.role == "admin":
        # Admins can delete any API key
        pass
    elif current_user.role == "apartment_admin":
        # Apartment admins can only delete API keys from their apartment
        key_owner = db.get_api_key_owner(api_key.user_id)
        if key_owner.apartment_id != current_user.apartment_id:
            raise APIException(
                status_code=403,
                detail="Cannot delete API keys for users from other apartments",
            )
    else:
        # Guests can only delete their own API keys
        if api_key.user_id != current_user.id:
            raise APIException(
                status_code=403,
                detail="You can only delete your own API keys",
            )

    if db.delete_api_key(key_suffix):
        return {"message": "API key deleted"}
    raise APIException(status_code=500, detail="Failed to delete API key")
