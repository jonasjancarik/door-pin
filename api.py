import uvicorn
import os
import boto3
import logging
from botocore.exceptions import ClientError, EndpointConnectionError
from fastapi import FastAPI, HTTPException, Depends, Request, status, Path
from fastapi.responses import JSONResponse, Response
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, EmailStr
import utils
from secrets import token_urlsafe
import random
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import db
from typing import Optional
from input_handler import read_input
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import date, time
from typing import List
import time as time_module

load_dotenv()

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=os.getenv("LOG_LEVEL", logging.INFO),
    datefmt="%Y-%m-%d %H:%M:%S",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    yield


app = FastAPI(lifespan=lifespan)

origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

rate_limit = defaultdict(list)
MAX_ATTEMPTS = 5
RATE_LIMIT_DURATION = 60  # 1 minute


def apartment_return_format(apartment: db.Apartment):
    return {
        "id": apartment.id,
        "number": apartment.number,
        "description": apartment.description,
    }


def user_return_format(user: db.User):
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "apartment": apartment_return_format(user.apartment),
        "role": user.role,
    }


def check_rate_limit(ip_address):
    now = time_module.time()
    request_times = rate_limit[ip_address]
    request_times = [t for t in request_times if now - t < RATE_LIMIT_DURATION]

    if len(request_times) >= MAX_ATTEMPTS:
        raise HTTPException(
            status_code=429, detail="Too many attempts. Please try again later."
        )

    request_times.append(now)
    rate_limit[ip_address] = request_times


# Auth models
class LoginRequest(BaseModel):
    email: EmailStr


class LoginCodeAttempt(BaseModel):
    email: EmailStr
    login_code: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str
    user: dict


# RFID models
class RFIDCreate(BaseModel):
    uuid: str
    label: str
    user_id: Optional[int] = None


class RFIDResponse(BaseModel):
    id: int
    label: str
    created_at: str
    user_id: int
    user_email: str
    last_four_digits: str


# PIN models
class PINCreate(BaseModel):
    pin: str
    label: str
    user_id: Optional[int] = None


class PINResponse(BaseModel):
    id: int
    label: str
    created_at: str
    user_id: int
    user_email: str


class PINUpdate(BaseModel):
    pin: Optional[str]
    label: Optional[str]


# Apartment models
class ApartmentCreate(BaseModel):
    number: str  # todo: yes number is string - we should rename "number" to "apartment_name" probably, because this doesn't have to be a numeric identifier
    description: Optional[str] = None


class ApartmentResponse(BaseModel):
    id: int
    number: str
    description: Optional[str]


class ApartmentUpdate(BaseModel):
    number: Optional[str]
    description: Optional[str] = None


# User models
class UserCreate(BaseModel):
    name: str
    email: EmailStr
    role: str
    apartment: ApartmentCreate  # we could also use another "ApartmentIdentifier" class here as we only need the number, but ApartmentCreate works


class UserResponse(BaseModel):
    id: int
    name: str
    email: EmailStr
    role: str
    apartment_number: int


class UserUpdate(BaseModel):
    name: Optional[str]
    email: Optional[EmailStr]
    role: Optional[str]
    apartment_number: Optional[int]


# Guest schedule models
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


# Track failed attempts
failed_attempts = defaultdict(int)
MAX_FAILED_ATTEMPTS = 3


class APIException(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail


def create_error_response(status_code: int, detail: str, type: str = "APIError"):
    return JSONResponse(
        status_code=status_code,
        content={"error": {"type": type, "detail": detail, "status_code": status_code}},
    )


@app.exception_handler(APIException)
async def api_exception_handler(request: Request, exc: APIException):
    return create_error_response(exc.status_code, exc.detail)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return create_error_response(exc.status_code, exc.detail)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return create_error_response(
        status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc), "ValidationError"
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    return create_error_response(
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        "An unexpected error occurred",
        "InternalServerError",
    )


@app.post("/auth/magic-links", status_code=status.HTTP_202_ACCEPTED)
def send_magic_link(request: LoginRequest):
    success_message = (
        "A login code has been sent to your email. Please enter the code below."
    )

    login_code = "".join(random.choices("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ", k=8))
    hashed_token = utils.hash_secret(login_code)
    email = request.email

    user = db.get_user(email)
    if user:
        db.save_login_code(
            user.id, hashed_token, int(time_module.time()) + 900
        )  # 15 minutes expiration
    else:
        logging.error(f"Login code requested for a non-existing user {email}.")
        return success_message  # for security reasons, we don't want to leak if the user exists

    url_to_use = os.getenv(
        "WEB_APP_URL", f"http://localhost:{os.getenv('WEB_APP_PORT', 8050)}/"
    )
    if not url_to_use.endswith("/"):
        url_to_use += "/"

    aws_region = os.getenv("AWS_REGION")
    if not aws_region:
        raise APIException(status_code=500, detail="Server configuration error")

    try:
        ses_client = boto3.client("ses", region_name=aws_region)
    except Exception:
        raise APIException(status_code=500, detail="Failed to initialize email service")

    sender = os.getenv("AWS_SES_SENDER_EMAIL")
    if not sender:
        raise APIException(status_code=500, detail="Server configuration error")

    subject = "Your Login Code"
    body_html = f"""<html><body><center><h1>Your Login Code</h1><p>Please use this code to log in:</p><p>{login_code}</p><p>Alternatively, you can click this link to log in: <a href='{url_to_use}?login_code={login_code}'>Log In</a></p></center></body></html>"""

    try:
        response = ses_client.send_email(
            Destination={"ToAddresses": [email]},
            Message={
                "Body": {"Html": {"Charset": "UTF-8", "Data": body_html}},
                "Subject": {"Charset": "UTF-8", "Data": subject},
            },
            Source=sender,
        )
        logging.info(f"Email sent: {response}")
        logging.debug(f"Login code: {login_code}")
        return success_message
    except EndpointConnectionError as e:
        logging.error(f"Failed to connect to AWS SES endpoint: {str(e)}")
        raise APIException(
            status_code=500,
            detail="Failed to connect to email service. Please check your AWS region configuration.",
        )
    except ClientError as e:
        logging.error(f"Failed to send email: {str(e)}")
        raise APIException(
            status_code=500,
            detail="Failed to send email. Please check your AWS SES configuration.",
        )
    except Exception as e:
        logging.error(f"Unexpected error while sending email: {str(e)}")
        raise APIException(
            status_code=500,
            detail="An unexpected error occurred while sending the email.",
        )


def authenticate_user(web_app_token: str = Depends(oauth2_scheme)) -> db.User:
    if user := db.get_user_by_token(web_app_token):
        return user
    raise APIException(status_code=401, detail="Unauthorized")


@app.post("/auth/verify", status_code=status.HTTP_200_OK)
def verify_authentication(request: Request, user: db.User = Depends(authenticate_user)):
    current_token = get_current_token(request)
    new_expiration = int(time_module.time()) + 31536000  # 1 year from now
    db.extend_token_expiration(current_token, new_expiration)
    return {"status": "authenticated", "user": user_return_format(user)}


def get_current_token(request: Request) -> str:
    authorization: str = request.headers.get("Authorization")
    if not authorization or not authorization.startswith("Bearer "):
        raise APIException(status_code=401, detail="Unauthorized")
    return authorization.replace("Bearer ", "")


@app.delete("/auth/tokens/current", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    user: db.User = Depends(authenticate_user),
    current_token: str = Depends(get_current_token),
):
    email = user.email
    user = db.get_user(email)
    if user:
        tokens = user.tokens if user.tokens else []
        if tokens and current_token in [token.token_hash for token in tokens]:
            token_to_remove = next(
                token for token in tokens if token.token_hash == current_token
            )
            db.delete_token(token_to_remove.id)
            return Response(status_code=status.HTTP_204_NO_CONTENT)

    raise APIException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")


@app.post(
    "/auth/tokens", response_model=AuthResponse, status_code=status.HTTP_201_CREATED
)
def exchange_code(login_attempt: LoginCodeAttempt, request: Request):
    check_rate_limit(request.client.host)

    email = login_attempt.email
    login_code = login_attempt.login_code

    if not login_code:
        raise APIException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid login code"
        )

    user = db.get_user_by_login_code(login_code)
    if not user or user.email != email:
        raise APIException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or login code",
        )

    # Check if the code has expired
    current_time = int(time_module.time())
    if db.is_login_code_expired(user.id, login_code, current_time):
        db.remove_login_code(user.id, login_code)
        raise APIException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Login code has expired. Please request a new one.",
        )

    # Code is valid, reset failed attempts
    if email in failed_attempts:
        del failed_attempts[email]

    # Generate and save new bearer token
    bearer_token = token_urlsafe(16)
    bearer_token_hashed = utils.hash_secret(bearer_token)
    db.save_token(
        user.id, bearer_token_hashed, int(time_module.time()) + 31536000
    )  # 1 year expiration

    # Remove the used login code
    db.remove_login_code(user.id, login_code)

    return {
        "access_token": bearer_token,
        "token_type": "bearer",
        "user": user_return_format(user),
    }


@app.post("/doors/unlock", status_code=status.HTTP_200_OK)
def unlock_door(_: db.User = Depends(authenticate_user)):
    utils.unlock_door()
    return {"message": "Door unlocked successfully"}


@app.post("/users", status_code=status.HTTP_201_CREATED)
def create_user(
    new_user: UserCreate, current_user: db.User = Depends(authenticate_user)
):
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

    return {
        "status": "user created",
        "user": user_return_format(created_user),
    }


@app.get("/users", status_code=status.HTTP_200_OK)
def list_users(current_user: db.User = Depends(authenticate_user)):
    if current_user.role == "admin":
        users = db.get_all_users()
    elif current_user.role == "apartment_admin":
        users = db.get_apartment_users(current_user.apartment.id)
    else:
        raise APIException(status_code=403, detail="Guests cannot list users")

    return [user_return_format(user) for user in users]


@app.get("/users/{user_id}", status_code=status.HTTP_200_OK)
def get_user(user_id: int, current_user: db.User = Depends(authenticate_user)):
    user = db.get_user(user_id)
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
    if not user:
        raise APIException(status_code=404, detail="User not found")
    return user


@app.put("/users/{user_id}", status_code=status.HTTP_200_OK)
def update_user(
    user_id: int, updated_user: dict, current_user: db.User = Depends(authenticate_user)
):
    if current_user.role != "admin":
        raise APIException(status_code=403, detail="Admin access required")
    try:
        updated_user_to_return = db.update_user(user_id, updated_user)
        if not updated_user_to_return:
            raise APIException(status_code=404, detail="User not found")
        return {
            "status": "User updated successfully",
            "user": {
                "id": updated_user_to_return.id,
                "name": updated_user_to_return.name,
                "email": updated_user_to_return.email,
                "apartment_number": updated_user_to_return.apartment.number,
                "role": updated_user_to_return.role,
            },
        }
    except ValueError as e:
        raise APIException(status_code=400, detail=str(e))


@app.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: int, current_user: db.User = Depends(authenticate_user)):
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


@app.post("/rfids", status_code=status.HTTP_201_CREATED)
def create_rfid(
    rfid_request: RFIDCreate, current_user: db.User = Depends(authenticate_user)
):
    salt = utils.generate_salt()
    hashed_uuid = utils.hash_secret(payload=rfid_request.uuid, salt=salt)
    last_four_digits = rfid_request.uuid[-4:]

    if rfid_request.user_id:
        target_user = db.get_user(rfid_request.user_id)
        if not target_user:
            raise APIException(status_code=404, detail="User not found")

        if current_user.role == "admin":
            # Admins can create RFIDs for any user
            user_id = target_user.id
        elif current_user.role == "apartment_admin":
            # Apartment admins can only create RFIDs for users in their apartment
            if target_user.apartment_id != current_user.apartment_id:
                raise APIException(
                    status_code=403,
                    detail="Cannot create RFIDs for users from other apartments",
                )
            user_id = target_user.id
        else:
            raise APIException(
                status_code=403,
                detail="Insufficient permissions to create RFIDs for other users",
            )
    else:
        # If no user_id is provided, create RFID for the current user
        user_id = current_user.id

    rfid = db.save_rfid(
        user_id, hashed_uuid, salt, last_four_digits, rfid_request.label
    )
    return {
        "status": "RFID created",
        "rfid": {
            "id": rfid.id,
            "label": rfid.label,
            "user_id": user_id,
            "last_four_digits": last_four_digits,
        },
    }


@app.get("/rfids/read", status_code=status.HTTP_200_OK)
async def read_rfid(timeout: int, user: db.User = Depends(authenticate_user)):
    logging.info(f"Attempting to read RFID with timeout: {timeout}")
    try:
        rfid_uuid = await read_input(timeout=timeout if timeout <= 30 else 30)
        if not rfid_uuid:
            logging.warning("RFID not found within the timeout period")
            raise APIException(status_code=404, detail="RFID not found")
        logging.info(f"Successfully read RFID: {rfid_uuid}")
        return {"uuid": rfid_uuid}
    except Exception as e:
        logging.error(f"Error reading RFID: {str(e)}")
        raise APIException(status_code=500, detail=f"Error reading RFID: {str(e)}")


@app.delete("/rfids/{rfid_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_rfid(rfid_id: int, current_user: db.User = Depends(authenticate_user)):
    rfid = db.get_rfid(rfid_id)
    if not rfid:
        raise APIException(status_code=404, detail="RFID not found")

    if current_user.role == "admin":
        # Admins can delete any RFID
        pass
    elif current_user.role == "apartment_admin":
        # Apartment admins can only delete RFIDs from their apartment
        if rfid.user.apartment_id != current_user.apartment_id:
            raise APIException(
                status_code=403,
                detail="Cannot delete RFIDs for users from other apartments",
            )
    elif current_user.role == "guest":
        # Guests can only delete their own RFIDs
        if rfid.user_id != current_user.id:
            raise APIException(
                status_code=403, detail="Guests can only delete their own RFIDs"
            )
    else:
        raise APIException(status_code=403, detail="Insufficient permissions")

    if db.delete_rfid(rfid_id):
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    raise APIException(status_code=500, detail="Failed to delete RFID")


@app.get("/rfids", status_code=status.HTTP_200_OK)
def list_rfids(current_user: db.User = Depends(authenticate_user)):
    if current_user.role == "admin":
        rfids = db.get_all_rfids()
    elif current_user.role == "apartment_admin":
        rfids = db.get_apartment_rfids(current_user.apartment.id)
    else:
        raise APIException(status_code=403, detail="Guests cannot list RFIDs")

    return [
        {
            "id": rfid.id,
            "label": rfid.label,
            "created_at": rfid.created_at,
            "user_id": rfid.user_id,
            "user_email": rfid.user.email,
            "last_four_digits": rfid.last_four_digits,
        }
        for rfid in rfids
    ]


@app.get("/users/{user_id}/rfids", status_code=status.HTTP_200_OK)
def list_user_rfids(
    user_id: int = Path(..., description="The ID of the user whose RFIDs to list"),
    current_user: db.User = Depends(authenticate_user),
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


@app.post("/pins", status_code=status.HTTP_201_CREATED)
def create_pin(
    pin_request: PINCreate, current_user: db.User = Depends(authenticate_user)
):
    salt = utils.generate_salt()
    hashed_pin = utils.hash_secret(payload=pin_request.pin, salt=salt)

    if pin_request.user_id:
        target_user = db.get_user(pin_request.user_id)
        if not target_user:
            raise APIException(status_code=404, detail="User not found")

        if current_user.role == "admin":
            # Admins can create PINs for any user
            user_id = target_user.id
        elif current_user.role == "apartment_admin":
            # Apartment admins can only create PINs for users in their apartment
            if target_user.apartment_id != current_user.apartment_id:
                raise APIException(
                    status_code=403,
                    detail="Cannot create PINs for users from other apartments",
                )
            user_id = target_user.id
        else:
            raise APIException(
                status_code=403,
                detail="Insufficient permissions to create PINs for other users",
            )
    else:
        # If no user_id is provided, create PIN for the current user
        user_id = current_user.id

    pin = db.save_pin(user_id, hashed_pin, pin_request.label, salt)
    return {
        "status": "PIN saved",
        "pin": {"id": pin.id, "label": pin.label, "user_id": user_id},
    }


@app.patch("/pins/{pin_id}", status_code=status.HTTP_200_OK)
def update_pin(
    pin_id: int, pin_request: PINCreate, user: db.User = Depends(authenticate_user)
):
    salt = utils.generate_salt()
    hashed_pin = utils.hash_secret(payload=pin_request.pin, salt=salt)
    pin = db.update_pin(pin_id, hashed_pin, pin_request.label, salt)
    if pin:
        return {"status": "PIN updated", "pin_id": pin.id}
    raise APIException(status_code=404, detail="PIN not found")


@app.delete("/pins/{pin_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_pin(pin_id: int, current_user: db.User = Depends(authenticate_user)):
    pin = db.get_pin(pin_id)
    if not pin:
        raise APIException(status_code=404, detail="PIN not found")

    if current_user.role == "admin":
        # Admins can delete any PIN
        pass
    elif current_user.role == "apartment_admin":
        # Apartment admins can only delete PINs from their apartment
        if pin.user.apartment_id != current_user.apartment_id:
            raise APIException(
                status_code=403,
                detail="Cannot delete PINs for users from other apartments",
            )
    elif current_user.role == "guest":
        # Guests can only delete their own PINs
        if pin.user_id != current_user.id:
            raise APIException(
                status_code=403, detail="Guests can only delete their own PINs"
            )
    else:
        raise APIException(status_code=403, detail="Insufficient permissions")

    if db.delete_pin(pin_id):
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    raise APIException(status_code=500, detail="Failed to delete PIN")


@app.get("/pins", status_code=status.HTTP_200_OK)
def list_pins(current_user: db.User = Depends(authenticate_user)):
    if current_user.role == "admin":
        pins = db.get_all_pins()
    elif current_user.role == "apartment_admin":
        pins = db.get_apartment_pins(current_user.apartment.id)
    else:
        raise APIException(status_code=403, detail="Guests cannot list PINs")

    return [
        {
            "id": pin.id,
            "label": pin.label,
            "created_at": pin.created_at,
            "user_id": pin.user_id,
            "user_email": pin.user.email,
        }
        for pin in pins
    ]


@app.get("/users/{user_id}/pins", status_code=status.HTTP_200_OK)
def list_user_pins(
    user_id: int = Path(..., description="User ID to fetch pins for"),
    current_user: db.User = Depends(authenticate_user),
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


@app.get("/apartments", status_code=status.HTTP_200_OK)
def list_apartments(user: db.User = Depends(authenticate_user)):
    if user.role != "admin":
        raise APIException(status_code=403, detail="Admin access required")
    return [apartment_return_format(apartment) for apartment in db.get_all_apartments()]


@app.post("/apartments", status_code=status.HTTP_201_CREATED)
def create_apartment(apartment: dict, user: db.User = Depends(authenticate_user)):
    if user.role != "admin":
        raise APIException(status_code=403, detail="Admin access required")
    new_apartment = db.add_apartment(apartment["number"], apartment.get("description"))
    return apartment_return_format(new_apartment)


@app.put("/apartments/{apartment_id}", status_code=status.HTTP_200_OK)
def update_apartment(
    apartment_id: int,
    updated_apartment: dict,
    user: db.User = Depends(authenticate_user),
):
    if user.role != "admin":
        raise APIException(status_code=403, detail="Admin access required")
    apartment = db.update_apartment(apartment_id, updated_apartment)
    if apartment:
        return apartment_return_format(apartment)
    raise APIException(status_code=404, detail="Apartment not found")


@app.delete("/apartments/{apartment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_apartment(apartment_id: int, user: db.User = Depends(authenticate_user)):
    if user.role != "admin":
        raise APIException(status_code=403, detail="Admin access required")
    if db.remove_apartment(apartment_id):
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    raise APIException(status_code=404, detail="Apartment not found")


@app.post("/guests/{user_id}/recurring-schedules", status_code=status.HTTP_201_CREATED)
def create_recurring_schedule(
    user_id: int,
    schedule: RecurringScheduleCreate,
    current_user: db.User = Depends(authenticate_user),
):
    if current_user.role not in ["admin", "apartment_admin"]:
        raise APIException(status_code=403, detail="Insufficient permissions")

    guest_user = db.get_user(user_id)
    if not guest_user or guest_user.role != "guest":
        raise APIException(status_code=400, detail="Invalid guest user")

    if (
        current_user.role == "apartment_admin"
        and guest_user.apartment_id != current_user.apartment_id
    ):
        raise APIException(
            status_code=403,
            detail="Cannot modify schedule for guests from other apartments",
        )

    new_schedule = db.add_recurring_schedule(
        user_id, schedule.day_of_week, schedule.start_time, schedule.end_time
    )
    return {"status": "Recurring schedule created", "schedule_id": new_schedule.id}


@app.post("/guests/{user_id}/one-time-accesses", status_code=status.HTTP_201_CREATED)
def create_one_time_access(
    user_id: int,
    access: OneTimeAccessCreate,
    current_user: db.User = Depends(authenticate_user),
):
    if current_user.role not in ["admin", "apartment_admin"]:
        raise APIException(status_code=403, detail="Insufficient permissions")

    guest_user = db.get_user(user_id)
    if not guest_user or guest_user.role != "guest":
        raise APIException(status_code=400, detail="Invalid guest user")

    if (
        current_user.role == "apartment_admin"
        and guest_user.apartment_id != current_user.apartment_id
    ):
        raise APIException(
            status_code=403,
            detail="Cannot modify access for guests from other apartments",
        )

    new_access = db.add_one_time_access(
        user_id, access.access_date, access.start_time, access.end_time
    )
    return {"status": "One-time access created", "access_id": new_access.id}


@app.get("/guests/{user_id}/schedules", status_code=status.HTTP_200_OK)
def list_guest_schedules(
    user_id: int,
    current_user: db.User = Depends(authenticate_user),
):
    if (
        current_user.role not in ["admin", "apartment_admin"]
        and current_user.id != user_id
    ):
        raise APIException(status_code=403, detail="Insufficient permissions")

    guest_user = db.get_user(user_id)
    if not guest_user or guest_user.role != "guest":
        raise APIException(status_code=400, detail="Invalid guest user")

    if (
        current_user.role == "apartment_admin"
        and guest_user.apartment_id != current_user.apartment_id
    ):
        raise APIException(
            status_code=403,
            detail="Cannot view schedules for guests from other apartments",
        )

    recurring_schedules = db.get_recurring_schedules_by_user(user_id)
    one_time_access = db.get_one_time_accesses_by_user(user_id)

    return {
        "recurring_schedules": [
            {
                "id": schedule.id,
                "day_of_week": schedule.day_of_week,
                "start_time": schedule.start_time.isoformat(),
                "end_time": schedule.end_time.isoformat(),
            }
            for schedule in recurring_schedules
        ],
        "one_time_access": [
            {
                "id": access.id,
                "access_date": access.access_date.isoformat(),
                "start_time": access.start_time.isoformat(),
                "end_time": access.end_time.isoformat(),
            }
            for access in one_time_access
        ],
    }


@app.delete(
    "/guests/recurring-schedules/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_recurring_schedule(
    schedule_id: int, current_user: db.User = Depends(authenticate_user)
):
    if current_user.role not in ["admin", "apartment_admin"]:
        raise APIException(status_code=403, detail="Insufficient permissions")

    schedule = db.get_recurring_schedule(schedule_id)
    if not schedule:
        raise APIException(status_code=404, detail="Schedule not found")

    if current_user.role == "apartment_admin":
        guest_user = db.get_user(schedule.user_id)

        if guest_user.apartment_id != current_user.apartment_id:
            raise APIException(
                status_code=403,
                detail="Cannot remove schedules for guests from other apartments",
            )

    if db.remove_recurring_schedule(schedule_id):
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    raise APIException(status_code=500, detail="Failed to delete recurring schedule")


@app.delete(
    "/guests/one-time-accesses/{access_id}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_one_time_access(
    access_id: int, current_user: db.User = Depends(authenticate_user)
):
    if current_user.role not in ["admin", "apartment_admin"]:
        raise APIException(status_code=403, detail="Insufficient permissions")

    access = db.get_one_time_access(access_id)
    if not access:
        raise APIException(status_code=404, detail="One-time access not found")

    if current_user.role == "apartment_admin":
        guest_user = db.get_user(access.user_id)
        if guest_user.apartment_id != current_user.apartment_id:
            raise APIException(
                status_code=403,
                detail="Cannot remove access for guests from other apartments",
            )

    if db.remove_one_time_access(access_id):
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    raise APIException(status_code=500, detail="Failed to delete one-time access")


if __name__ == "__main__":
    port = int(os.environ.get("API_PORT", 8000))
    uvicorn.run(app, host=os.environ.get("API_HOST", "localhost"), port=port)
