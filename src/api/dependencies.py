from fastapi import Depends, Request, Security
from fastapi.security import OAuth2PasswordBearer
from .exceptions import APIException
from fastapi.security import APIKeyHeader
from sqlalchemy.orm import Session
from src.db import get_db
from src.api.utils import verify_api_key
from src.db import User
from src.utils import hash_secret

api_key_header = APIKeyHeader(name="X-API-Key")


async def get_current_user_from_api_key(
    api_key: str = Security(api_key_header), db: Session = Depends(get_db)
) -> User:
    api_key_obj = verify_api_key(db, api_key)
    if not api_key_obj:
        raise APIException(status_code=401, detail="Invalid API Key")
    return api_key_obj.user


async def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    # Check for API key in header
    api_key = request.headers.get("X-API-Key")

    # Check for API key in query parameters if not in header
    if not api_key:
        api_key = request.query_params.get("api_key")

    if api_key:
        with db as session:  # Use the context manager properly
            api_key_obj = verify_api_key(session, api_key)
        if api_key_obj:
            return api_key_obj.user

    # If no API key or invalid, fall back to bearer token authentication
    authorization: str = request.headers.get("Authorization")
    if not authorization or not authorization.startswith("Bearer "):
        raise APIException(status_code=401, detail="No valid authentication provided")

    token = authorization.replace("Bearer ", "")
    with db as session:  # Use the context manager properly
        token_hash = hash_secret(token)
        user = (
            session.query(User).filter(User.tokens.any(token_hash=token_hash)).first()
        )
    if user:
        return user
    raise APIException(status_code=401, detail="Invalid authentication")


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


def authenticate_user(
    web_app_token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> User:
    with db as session:  # Use the context manager properly
        user = (
            session.query(User)
            .filter(User.tokens.any(token_hash=web_app_token))
            .first()
        )
    if user:
        return user
    raise APIException(status_code=401, detail="Unauthorized")


def get_current_token(request: Request) -> str:
    authorization: str = request.headers.get("Authorization")
    if not authorization or not authorization.startswith("Bearer "):
        raise APIException(status_code=401, detail="Unauthorized")
    return authorization.replace("Bearer ", "")
