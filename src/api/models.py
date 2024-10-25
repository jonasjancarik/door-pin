from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import date, time

# Include all the Pydantic models here
# (LoginRequest, LoginCodeAttempt, AuthResponse, RFIDCreate, RFIDResponse, etc.)


class LoginRequest(BaseModel):
    email: EmailStr


class LoginCodeAttempt(BaseModel):
    email: EmailStr
    login_code: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str
    user: dict


class RFIDCreate(BaseModel):
    uuid: str
    label: Optional[str] = None
    user_id: Optional[int] = None


class RFIDResponse(BaseModel):
    id: int
    label: str
    created_at: str
    user_id: int
    user_email: str
    last_four_digits: str


class PINCreate(BaseModel):
    pin: Optional[str] = None
    label: Optional[str] = None
    user_id: Optional[int] = None


class PINResponse(BaseModel):
    id: int
    label: str
    created_at: str
    user_id: int
    user_email: str
    pin: Optional[str] = None  # Only included for guest users when creating new PINs


class PINUpdate(BaseModel):
    pin: Optional[str] = None
    label: Optional[str] = None


class ApartmentCreate(BaseModel):
    number: str
    description: Optional[str] = None


class ApartmentResponse(BaseModel):
    id: int
    number: str
    description: Optional[str]


class ApartmentUpdate(BaseModel):
    number: Optional[str]
    description: Optional[str] = None


class User(BaseModel):
    id: int
    name: str
    email: str
    role: str
    apartment_id: int
    apartment: ApartmentResponse

    class Config:
        orm_mode = True  # This tells Pydantic to work with ORM models


class UserCreate(BaseModel):
    name: str
    email: EmailStr
    role: str
    apartment: ApartmentCreate


class UserResponse(BaseModel):
    id: int
    name: str
    email: EmailStr
    role: str
    apartment: ApartmentResponse


class UserUpdate(BaseModel):
    name: Optional[str]
    email: Optional[EmailStr]
    role: Optional[str]
    apartment_number: Optional[int]


class RecurringScheduleCreate(BaseModel):
    day_of_week: int
    start_time: time
    end_time: time


class OneTimeAccessCreate(BaseModel):
    access_date: date
    start_time: time
    end_time: time


class RecurringScheduleResponse(BaseModel):
    id: int
    day_of_week: int
    start_time: str
    end_time: str


class OneTimeAccessResponse(BaseModel):
    id: int
    access_date: str
    start_time: str
    end_time: str


class GuestSchedulesResponse(BaseModel):
    recurring_schedules: List[RecurringScheduleResponse]
    one_time_access: List[OneTimeAccessResponse]


class APIKeyCreate(BaseModel):
    description: str
    user_id: Optional[int] = None


class APIKeyResponse(BaseModel):
    key_prefix: str
    description: str
    created_at: str
    is_active: bool
    user_id: int

    class Config:
        from_attributes = True


class APIKeyWithSecret(APIKeyResponse):
    api_key: str


class VerifyAuthResponse(BaseModel):
    status: str
    user: dict
