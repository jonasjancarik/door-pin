from pydantic import BaseModel
from datetime import datetime


class APIKeyCreate(BaseModel):
    description: str


class APIKeyResponse(BaseModel):
    key_prefix: str
    description: str
    created_at: datetime
    is_active: bool

    class Config:
        from_attributes = True


class APIKeyWithSecret(APIKeyResponse):
    api_key: str
