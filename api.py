import uvicorn
import os
import time
import boto3
import logging
from botocore.exceptions import ClientError, EndpointConnectionError
from fastapi import FastAPI, HTTPException, Depends, Request, Query, status
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


def check_rate_limit(ip_address):
    now = time.time()
    request_times = rate_limit[ip_address]
    request_times = [t for t in request_times if now - t < RATE_LIMIT_DURATION]

    if len(request_times) >= MAX_ATTEMPTS:
        raise HTTPException(
            status_code=429, detail="Too many attempts. Please try again later."
        )

    request_times.append(now)
    rate_limit[ip_address] = request_times


class Token(BaseModel):
    access_token: str
    token_type: str


class LoginRequest(BaseModel):
    email: EmailStr


class AuthResponse(BaseModel):
    access_token: str
    token_type: str
    user: dict


class RFIDRequest(BaseModel):
    uuid: str
    label: str
    user_email: Optional[EmailStr] = None


class PinRequest(BaseModel):
    pin: str
    label: str


class LoginCodeAttempt(BaseModel):
    email: EmailStr
    login_code: str


class RecurringScheduleRequest(BaseModel):
    user_id: int
    day_of_week: int
    start_time: time
    end_time: time


class OneTimeAccessRequest(BaseModel):
    user_id: int
    access_date: date
    start_time: time
    end_time: time


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
            user.id, hashed_token, int(time.time()) + 900
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
    except Exception as e:
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
    raise HTTPException(status_code=401, detail="Unauthorized")


@app.post("/auth/verify", status_code=status.HTTP_200_OK)
def verify_authentication(user: db.User = Depends(authenticate_user)):
    return {"status": "authenticated", "user": user}


def get_current_token(request: Request) -> str:
    authorization: str = request.headers.get("Authorization")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")
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
    current_time = int(time.time())
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
        user.id, bearer_token_hashed, int(time.time()) + 31536000
    )  # 1 year expiration

    # Remove the used login code
    db.remove_login_code(user.id, login_code)

    return {
        "access_token": bearer_token,
        "token_type": "bearer",
        "user": {
            "apartment_number": user.apartment.number,
            "email": user.email,
            "name": user.name,
            "role": user.role,
        },
    }


@app.post("/doors/unlock", status_code=status.HTTP_200_OK)
def unlock_door(_: db.User = Depends(authenticate_user)):
    utils.unlock_door()
    return {"message": "Door unlocked successfully"}


@app.post("/users", status_code=status.HTTP_201_CREATED)
def create_user(new_user: dict, current_user: db.User = Depends(authenticate_user)):
    if current_user.role == "guest":
        raise APIException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Guests cannot create users"
        )

    if not new_user.get("apartment_number") or not new_user.get("email"):
        raise APIException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing apartment number or email",
        )

    if new_user.get("role") == "admin" and current_user.role != "admin":
        raise APIException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can create admin users",
        )

    apartment = db.get_apartment_by_number(new_user.get("apartment_number"))
    if not apartment:
        raise APIException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Apartment with number {new_user.get('apartment_number')} not found",
        )

    if apartment.id != current_user.apartment.id and current_user.role != "admin":
        raise APIException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only create users for your own apartment",
        )

    existing_user = db.get_user(new_user.get("email"))
    if existing_user:
        raise APIException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"User with email {new_user.get('email')} already exists",
        )

    new_user["creator_id"] = current_user.id
    new_user["apartment_id"] = apartment.id
    new_user["role"] = new_user.get("role", "apartment_admin")
    created_user = db.add_user(new_user)

    return {
        "status": "user created",
        "user": {
            "id": created_user.id,
            "name": created_user.name,
            "email": created_user.email,
            "apartment_number": apartment.number,
            "role": created_user.role,
        },
    }


@app.get("/users", status_code=status.HTTP_200_OK)
def list_users(current_user: db.User = Depends(authenticate_user)):
    if current_user.role == "admin":
        users = db.get_all_users()
    elif current_user.role == "apartment_admin":
        users = db.get_apartment_users(current_user.apartment.id)
    else:
        raise APIException(status_code=403, detail="Guests cannot list users")

    return [
        {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "role": user.role,
            "apartment_number": user.apartment.number,
        }
        for user in users
    ]


@app.put("/users/{user_id}", status_code=status.HTTP_200_OK)
def update_user(
    user_id: int, updated_user: dict, current_user: db.User = Depends(authenticate_user)
):
    if current_user.role != "admin":
        raise APIException(status_code=403, detail="Admin access required")
    user = db.get_user(user_id)
    if not user:
        raise APIException(status_code=404, detail="User not found")
    updated_user["id"] = user_id
    db.save_user(updated_user)
    return {"status": "User updated successfully"}


@app.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: int, current_user: db.User = Depends(authenticate_user)):
    if current_user.role != "admin":
        raise APIException(status_code=403, detail="Admin access required")
    if db.remove_user(user_id):
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    raise APIException(status_code=404, detail="User not found")


@app.post("/rfids", status_code=status.HTTP_201_CREATED)
def create_rfid(
    rfid_request: RFIDRequest, current_user: db.User = Depends(authenticate_user)
):
    hashed_uuid = utils.hash_secret(payload=rfid_request.uuid)
    last_four_digits = rfid_request.uuid[-4:]

    if rfid_request.user_email:
        if current_user.role != "admin":
            raise APIException(
                status_code=403,
                detail="Only admin users can create RFIDs for other users",
            )

        target_user = db.get_user(rfid_request.user_email)
        if not target_user:
            raise APIException(status_code=404, detail="User not found")
        user_id = target_user.id
    else:
        user_id = current_user.id

    db.save_rfid(user_id, hashed_uuid, last_four_digits, rfid_request.label)
    return {
        "status": "RFID created",
        "user_email": rfid_request.user_email or current_user.email,
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


@app.delete("/rfids/{user_id}/{hashed_uuid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_rfid(
    user_id: int, hashed_uuid: str, user: db.User = Depends(authenticate_user)
):
    if db.delete_rfid(user_id, hashed_uuid):
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    raise APIException(status_code=404, detail="RFID not found")


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
    user_id: int = Query(..., description="User ID to fetch RFIDs for"),
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
def create_pin(pin_request: PinRequest, user: db.User = Depends(authenticate_user)):
    hashed_pin = utils.hash_secret(payload=pin_request.pin)
    user_id = db.get_user(user.email).id
    pin = db.save_pin(user_id, hashed_pin, pin_request.label)
    return {"status": "PIN saved", "pin_id": pin.id}


@app.patch("/pins/{pin_id}", status_code=status.HTTP_200_OK)
def update_pin(
    pin_id: int, pin_request: PinRequest, user: db.User = Depends(authenticate_user)
):
    hashed_pin = utils.hash_secret(payload=pin_request.pin)
    pin = db.update_pin(pin_id, hashed_pin, pin_request.label)
    if pin:
        return {"status": "PIN updated", "pin_id": pin.id}
    raise APIException(status_code=404, detail="PIN not found")


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
    user_id: int = Query(..., description="User ID to fetch pins for"),
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
    apartments = db.get_all_apartments()
    return [
        {
            "id": apartment.id,
            "number": apartment.number,
            "description": apartment.description,
        }
        for apartment in apartments
    ]


@app.post("/apartments", status_code=status.HTTP_201_CREATED)
def create_apartment(apartment: dict, user: db.User = Depends(authenticate_user)):
    if user.role != "admin":
        raise APIException(status_code=403, detail="Admin access required")
    new_apartment = db.add_apartment(apartment["number"], apartment.get("description"))
    return {
        "id": new_apartment.id,
        "number": new_apartment.number,
        "description": new_apartment.description,
    }


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
        return {
            "id": apartment.id,
            "number": apartment.number,
            "description": apartment.description,
        }
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
    schedule: RecurringScheduleRequest,
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

    new_schedule = db.add_recurring_guest_schedule(
        user_id, schedule.day_of_week, schedule.start_time, schedule.end_time
    )
    return {"status": "Recurring schedule created", "schedule_id": new_schedule.id}


@app.post("/guests/{user_id}/one-time-accesses", status_code=status.HTTP_201_CREATED)
def create_one_time_access(
    user_id: int,
    access: OneTimeAccessRequest,
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

    new_access = db.add_one_time_guest_access(
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

    recurring_schedules = db.get_user_recurring_schedules(user_id)
    one_time_access = db.get_user_one_time_access(user_id)

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

    schedule = db.get_recurring_guest_schedule(schedule_id)
    if not schedule:
        raise APIException(status_code=404, detail="Schedule not found")

    if current_user.role == "apartment_admin":
        guest_user = db.get_user(schedule.user_id)
        if guest_user.apartment_id != current_user.apartment_id:
            raise APIException(
                status_code=403,
                detail="Cannot remove schedules for guests from other apartments",
            )

    if db.remove_recurring_guest_schedule(schedule_id):
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

    access = db.get_one_time_guest_access(access_id)
    if not access:
        raise APIException(status_code=404, detail="One-time access not found")

    if current_user.role == "apartment_admin":
        guest_user = db.get_user(access.user_id)
        if guest_user.apartment_id != current_user.apartment_id:
            raise APIException(
                status_code=403,
                detail="Cannot remove access for guests from other apartments",
            )

    if db.remove_one_time_guest_access(access_id):
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    raise APIException(status_code=500, detail="Failed to delete one-time access")


if __name__ == "__main__":
    port = int(os.environ.get("API_PORT", 8000))
    uvicorn.run(app, host=os.environ.get("API_HOST", "localhost"), port=port)
