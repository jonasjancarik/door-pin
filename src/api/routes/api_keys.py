from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import List
import secrets
import hashlib
from src.db import get_db
from src.db import APIKey
from src.api.schemas.api_key import APIKeyCreate, APIKeyResponse, APIKeyWithSecret
from src.api.dependencies import get_current_user
from src.db import User

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
    api_key, prefix, key_hash = generate_api_key()

    db_api_key = APIKey(
        key_prefix=prefix,
        key_hash=key_hash,
        description=data.description,
        user_id=current_user.id,
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
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    return db.query(APIKey).filter(APIKey.user_id == current_user.id).all()


@router.delete("/{key_prefix}")
async def delete_api_key(
    key_prefix: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    api_key = (
        db.query(APIKey)
        .filter(APIKey.key_prefix == key_prefix, APIKey.user_id == current_user.id)
        .first()
    )
    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")

    db.delete(api_key)
    db.commit()
    return {"message": "API key deleted"}
