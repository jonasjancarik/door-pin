from fastapi import Depends, Request
from fastapi.security import OAuth2PasswordBearer
from .exceptions import APIException
import src.db as db

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


def authenticate_user(web_app_token: str = Depends(oauth2_scheme)) -> db.User:
    if user := db.get_user_by_token(web_app_token):
        return user
    raise APIException(status_code=401, detail="Unauthorized")


def get_current_token(request: Request) -> str:
    authorization: str = request.headers.get("Authorization")
    if not authorization or not authorization.startswith("Bearer "):
        raise APIException(status_code=401, detail="Unauthorized")
    return authorization.replace("Bearer ", "")
