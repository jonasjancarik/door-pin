import uvicorn
import os
import time
import boto3
import logging
from botocore.exceptions import ClientError, EndpointConnectionError
from fastapi import FastAPI, HTTPException, Depends, Request, Query
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

load_dotenv()

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=os.getenv("LOG_LEVEL", logging.INFO),
    datefmt="%Y-%m-%d %H:%M:%S",
)

app = FastAPI()

origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


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


@app.on_event("startup")
def on_startup():
    db.init_db()


@app.post("/auth/send-magic-link")
def send_magic_link(request: LoginRequest):
    success_message = (
        "A login code has been sent to your email. Please enter the code below."
    )

    login_code = "".join(random.choices("0123456789", k=6))
    hashed_token = utils.hash_secret(login_code)
    email = request.email

    user = db.get_user(email)
    if user:
        db.save_login_code(user.id, hashed_token, int(time.time()) + 3600)
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
        logging.error("AWS_REGION environment variable is not set")
        raise HTTPException(status_code=500, detail="Server configuration error")

    try:
        ses_client = boto3.client("ses", region_name=aws_region)
    except Exception as e:
        logging.error(f"Failed to create SES client: {str(e)}")
        raise HTTPException(
            status_code=500, detail="Failed to initialize email service"
        )

    sender = os.getenv("AWS_SES_SENDER_EMAIL")
    if not sender:
        logging.error("AWS_SES_SENDER_EMAIL environment variable is not set")
        raise HTTPException(status_code=500, detail="Server configuration error")

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
        raise HTTPException(
            status_code=500,
            detail="Failed to connect to email service. Please check your AWS region configuration.",
        )
    except ClientError as e:
        logging.error(f"Failed to send email: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to send email. Please check your AWS SES configuration.",
        )
    except Exception as e:
        logging.error(f"Unexpected error while sending email: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred while sending the email.",
        )


def authenticate_user(web_app_token: str = Depends(oauth2_scheme)) -> db.User:
    if user := db.get_user_by_token(web_app_token):
        return user
    raise HTTPException(status_code=401, detail="Unauthorized")


@app.post("/auth/verify")
def verify_authentication(user: db.User = Depends(authenticate_user)):
    return {"status": "authenticated", "user": user}


def get_current_token(request: Request) -> str:
    authorization: str = request.headers.get("Authorization")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")
    return authorization.replace("Bearer ", "")


@app.post("/auth/logout")
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
            return {"status": "logged out"}

    raise HTTPException(status_code=401, detail="Unauthorized")


class LoginCode(BaseModel):
    login_code: str


@app.post("/auth/exchange-code", response_model=AuthResponse)
def exchange_code(login_code: LoginCode):
    if not login_code.login_code:
        raise HTTPException(status_code=400, detail="Invalid login code")

    user = db.get_user_by_login_code(login_code.login_code)
    if user:
        bearer_token = token_urlsafe(16)
        bearer_token_hashed = utils.hash_secret(bearer_token)
        db.save_token(
            user.id, bearer_token_hashed, int(time.time()) + 31536000
        )  # 1 year expiration

        # remove login code
        db.remove_login_code(user.id, login_code.login_code)

        return {
            "access_token": bearer_token,
            "token_type": "bearer",
            "user": {
                "apartment_number": user.apartment.number,
                "email": user.email,
                "name": user.name,
                "admin": user.admin,
            },
        }

    raise HTTPException(status_code=401, detail="Invalid or expired login code")


@app.post("/door/unlock")
def unlock_door(_: db.User = Depends(authenticate_user)):
    utils.unlock_door()
    return {"message": "Door unlocked successfully"}


@app.post("/users/create")
def create_user(new_user: dict, current_user: db.User = Depends(authenticate_user)):
    if current_user.guest:
        raise HTTPException(status_code=403, detail="Guests cannot create users")

    apartment = db.get_apartment_by_number(new_user["apartment_number"])
    if not apartment:
        raise HTTPException(status_code=404, detail="Apartment not found")

    if apartment.id != current_user.apartment.id and not current_user.admin:
        raise HTTPException(
            status_code=403, detail="You can only create users for your own apartment"
        )

    existing_user = db.get_user(new_user["email"])
    if existing_user:
        raise HTTPException(
            status_code=409, detail="User with this email already exists"
        )

    new_user["creator_id"] = current_user.id
    new_user["apartment_id"] = apartment.id
    created_user = db.add_user(new_user)

    return {
        "status": "user created",
        "user": {
            "id": created_user.id,
            "name": created_user.name,
            "email": created_user.email,
            "apartment_number": apartment.number,
            "guest": created_user.guest,
        },
    }


@app.post("/rfid/register")
def register_rfid(
    rfid_request: RFIDRequest, current_user: db.User = Depends(authenticate_user)
):
    hashed_uuid = utils.hash_secret(payload=rfid_request.uuid)
    last_four_digits = rfid_request.uuid[-4:]

    # If user_email is provided, check if the current user is an admin
    if rfid_request.user_email:
        if not current_user.admin:
            raise HTTPException(
                status_code=403,
                detail="Only admin users can register RFIDs for other users",
            )

        target_user = db.get_user(rfid_request.user_email)
        if not target_user:
            raise HTTPException(status_code=404, detail="User not found")
        user_id = target_user.id
    else:
        user_id = current_user.id

    db.save_rfid(user_id, hashed_uuid, last_four_digits, rfid_request.label)
    return {
        "status": "RFID created",
        "user_email": rfid_request.user_email or current_user.email,
    }


@app.get("/rfid/read")
async def read_rfid(timeout: int, user: db.User = Depends(authenticate_user)):
    logging.info(f"Attempting to read RFID with timeout: {timeout}")
    try:
        rfid_uuid = await read_input(timeout=timeout if timeout <= 30 else 30)
        if not rfid_uuid:
            logging.warning("RFID not found within the timeout period")
            raise HTTPException(status_code=404, detail="RFID not found")
        logging.info(f"Successfully read RFID: {rfid_uuid}")
        return {"uuid": rfid_uuid}
    except Exception as e:
        logging.error(f"Error reading RFID: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error reading RFID: {str(e)}")


@app.delete("/rfid/delete")
def delete_rfid(
    user_id: int, hashed_uuid: str, user: db.User = Depends(authenticate_user)
):
    if db.delete_rfid(user_id, hashed_uuid):
        return {"status": "RFID deleted"}
    raise HTTPException(status_code=404, detail="RFID not found")


@app.get("/rfid/list")
def list_rfids(current_user: db.User = Depends(authenticate_user)):
    if current_user.admin:
        rfids = db.get_all_rfids()
    elif not current_user.guest:
        rfids = db.get_apartment_rfids(current_user.apartment.id)
    else:
        raise HTTPException(status_code=403, detail="Guests cannot list RFIDs")

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


@app.get("/rfid/list/user")
def list_user_rfids(
    user_id: Optional[int] = Query(
        None, description="Optional user ID to fetch RFIDs for"
    ),
    current_user: db.User = Depends(authenticate_user),
):
    if user_id is None:
        # If no user_id is provided, return RFIDs for the current user
        rfids = db.get_user_rfids(current_user.id)
    else:
        # Check permissions based on user role
        if current_user.admin:
            # Admin can get any user's RFIDs
            rfids = db.get_user_rfids(user_id)
        elif (
            not current_user.guest
            and current_user.apartment_id == db.get_user(user_id).apartment_id
        ):
            # Non-guest users can get RFIDs of users from their apartment
            rfids = db.get_user_rfids(user_id)
        elif current_user.id == user_id:
            # Guests can only get their own RFIDs
            rfids = db.get_user_rfids(user_id)
        else:
            raise HTTPException(status_code=403, detail="Insufficient permissions")

    return [
        {
            "id": rfid.id,
            "label": rfid.label,
            "created_at": rfid.created_at,
            "last_four_digits": rfid.last_four_digits,
        }
        for rfid in rfids
    ]


@app.post("/pin/create")
def create_pin(pin_request: PinRequest, user: db.User = Depends(authenticate_user)):
    hashed_pin = utils.hash_secret(payload=pin_request.pin)
    user_id = db.get_user(user.email).id
    pin = db.save_pin(user_id, hashed_pin, pin_request.label)
    return {"status": "PIN saved", "pin_id": pin.id}


@app.post(
    "/pin/update/{pin_id}"
)  # todo: this should serve to update the pin label only
def update_pin(
    pin_id: int, pin_request: PinRequest, user: db.User = Depends(authenticate_user)
):
    hashed_pin = utils.hash_secret(payload=pin_request.pin)
    pin = db.update_pin(pin_id, hashed_pin, pin_request.label)
    if pin:
        return {"status": "PIN updated", "pin_id": pin.id}
    raise HTTPException(status_code=404, detail="PIN not found")


@app.get("/pin/list")
def list_pins(current_user: db.User = Depends(authenticate_user)):
    if current_user.admin:
        pins = db.get_all_pins()
    elif not current_user.guest:
        pins = db.get_apartment_pins(current_user.apartment.id)
    else:
        raise HTTPException(status_code=403, detail="Guests cannot list PINs")

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


@app.get("/pin/list/user")
def list_user_pins(
    user_id: Optional[int] = Query(
        None, description="Optional user ID to fetch pins for"
    ),
    current_user: db.User = Depends(authenticate_user),
):
    if user_id is None:
        # If no user_id is provided, return pins for the current user
        pins = db.get_user_pins(current_user.id)
    else:
        # Check permissions based on user role
        if current_user.admin:
            # Admin can get any user's pins
            pins = db.get_user_pins(user_id)
        elif (
            not current_user.guest
            and current_user.apartment_id == db.get_user(user_id).apartment_id
        ):
            # Non-guest users can get pins of users from their apartment
            pins = db.get_user_pins(user_id)
        elif current_user.id == user_id:
            # Guests can only get their own pins
            pins = db.get_user_pins(user_id)
        else:
            raise HTTPException(status_code=403, detail="Insufficient permissions")

    return [
        {
            "id": pin.id,
            "label": pin.label,
            "created_at": pin.created_at,
        }
        for pin in pins
    ]


@app.get("/users/list")
def list_users(current_user: db.User = Depends(authenticate_user)):
    if current_user.admin:
        users = db.get_all_users()
    elif not current_user.guest:
        users = db.get_apartment_users(current_user.apartment.id)
    else:
        raise HTTPException(status_code=403, detail="Guests cannot list users")

    return [
        {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "admin": user.admin,
            "guest": user.guest,
            "apartment_number": user.apartment.number,
        }
        for user in users
    ]


@app.put("/users/update/{user_id}")
def update_user(
    user_id: int, updated_user: dict, current_user: db.User = Depends(authenticate_user)
):
    if not current_user.admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    user = db.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    updated_user["id"] = user_id
    db.save_user(updated_user)
    return {"status": "User updated successfully"}


@app.delete("/users/delete/{user_id}")
def delete_user(user_id: int, current_user: db.User = Depends(authenticate_user)):
    if not current_user.admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    if db.remove_user(user_id):
        return {"status": "User deleted successfully"}
    raise HTTPException(status_code=404, detail="User not found")


@app.get("/apartments/list")
def list_apartments(user: db.User = Depends(authenticate_user)):
    if not user.admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    apartments = db.get_all_apartments()
    return [
        {
            "id": apartment.id,
            "number": apartment.number,
            "description": apartment.description,
        }
        for apartment in apartments
    ]


@app.post("/apartments/create")
def create_apartment(apartment: dict, user: db.User = Depends(authenticate_user)):
    if not user.admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    new_apartment = db.add_apartment(apartment["number"], apartment.get("description"))
    return {
        "id": new_apartment.id,
        "number": new_apartment.number,
        "description": new_apartment.description,
    }


@app.put("/apartments/update/{apartment_id}")
def update_apartment(
    apartment_id: int,
    updated_apartment: dict,
    user: db.User = Depends(authenticate_user),
):
    if not user.admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    apartment = db.update_apartment(apartment_id, updated_apartment)
    if apartment:
        return {
            "id": apartment.id,
            "number": apartment.number,
            "description": apartment.description,
        }
    raise HTTPException(status_code=404, detail="Apartment not found")


@app.delete("/apartments/delete/{apartment_id}")
def delete_apartment(apartment_id: int, user: db.User = Depends(authenticate_user)):
    if not user.admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    if db.remove_apartment(apartment_id):
        return {"status": "Apartment deleted successfully"}
    raise HTTPException(status_code=404, detail="Apartment not found")


if __name__ == "__main__":
    port = int(os.environ.get("API_PORT", 8000))
    uvicorn.run(app, host=os.environ.get("API_HOST", "localhost"), port=port)
