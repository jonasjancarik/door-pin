from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
import secrets
import hashlib
from src.db import get_db
from src.db import APIKey
from src.api.models import APIKeyCreate, APIKeyResponse, APIKeyWithSecret
from src.api.dependencies import get_current_user
from src.db import User
from src.api.exceptions import APIException

router = APIRouter(prefix="/api-keys", tags=["API Keys"])


def generate_api_key() -> tuple[str, str, str]:
    """Generate a new API key, its prefix, and hash."""
    api_key = secrets.token_urlsafe(32)
    prefix = api_key[:8]
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    return api_key, prefix, key_hash


@router.post("", response_model=APIKeyWithSecret)
async def create_api_key(
    data: APIKeyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role == "guest":
        raise APIException(
            status_code=403,
            detail="Guests cannot create API keys",
        )

    # If a user_id is provided in the request, we're creating a key for another user
    if data.user_id:
        target_user = db.query(User).filter(User.id == data.user_id).first()
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

    api_key, prefix, key_hash = generate_api_key()

    db_api_key = APIKey(
        key_prefix=prefix,
        key_hash=key_hash,
        description=data.description,
        user_id=user_id,
    )

    db.add(db_api_key)
    db.commit()
    db.refresh(db_api_key)

    return APIKeyWithSecret(
        key_prefix=prefix,
        description=data.description,
        created_at=db_api_key.created_at,
        is_active=db_api_key.is_active,
        api_key=api_key,
    )


@router.get("", response_model=List[APIKeyResponse])
async def list_api_keys(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role == "admin":
        return db.query(APIKey).all()
    elif current_user.role == "apartment_admin":
        return (
            db.query(APIKey)
            .join(User)
            .filter(User.apartment_id == current_user.apartment_id)
            .all()
        )
    else:
        # Guests can only see their own API keys
        return db.query(APIKey).filter(APIKey.user_id == current_user.id).all()


@router.delete("/{key_prefix}")
async def delete_api_key(
    key_prefix: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    api_key = db.query(APIKey).filter(APIKey.key_prefix == key_prefix).first()
    if not api_key:
        raise APIException(status_code=404, detail="API key not found")

    if current_user.role == "admin":
        # Admins can delete any API key
        pass
    elif current_user.role == "apartment_admin":
        # Apartment admins can only delete API keys from their apartment
        key_owner = db.query(User).filter(User.id == api_key.user_id).first()
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

    db.delete(api_key)
    db.commit()
    return {"message": "API key deleted"}
