# main.py
import uvicorn
import os
import time
import boto3
import logging
from botocore.exceptions import ClientError
from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, EmailStr
import utils
from secrets import token_urlsafe

app = FastAPI()

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


@app.post("/send-magic-link")
def send_magic_link_endpoint(request: LoginRequest):
    login_code = token_urlsafe(8)  # Generate a short-lived login code
    data = utils.load_data()
    for apartment_number, apartment_data in data["apartments"].items():
        for user in apartment_data["users"]:
            if user["email"] == request.email:
                user["login_codes"].append(
                    {
                        "hash": utils.hash_secret(login_code),
                        "expiration": int(time.time()) + 300,
                    }
                )
                utils.save_data(data)
                return send_magic_link(request.email, login_code)
    raise HTTPException(status_code=400, detail="Email not found")


def send_magic_link(email):
    login_code = token_urlsafe(16)
    hashed_token = utils.hash_secret(login_code)

    data = utils.load_data()
    for apartment_number in data["apartments"]:
        for user in data["apartments"][apartment_number]["users"]:
            if user["email"] == email:
                user_tokens = user.setdefault("tokens", [])
                user_tokens.append(
                    {
                        "hash": hashed_token,
                        "expiration": int(time.time()) + 31536000,
                    }  # 1 year expiration
                )
                break
        else:
            data["apartments"][apartment_number]["users"].append(
                {"email": email, "name": email, "token_hashes": [hashed_token]}
            )
    utils.save_data(data)

    url_to_use = os.getenv(
        "WEB_APP_URL", f"http://localhost:{os.getenv('WEB_APP_PORT', 8050)}/"
    )
    if not url_to_use.endswith("/"):
        url_to_use += "/"
    ses_client = boto3.client("ses", region_name=os.getenv("AWS_REGION"))
    sender = os.getenv("AWS_SES_SENDER_EMAIL")
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
        print(f"Email sent! {response}")
        return "A login code has been sent to your email. Please enter the code below or click the link in the email."
    except ClientError as e:
        logging.error(f"Failed to send email: {e}")
        raise HTTPException(status_code=500, detail="Failed to send email.")


def authenticate_user(web_app_token: str = Depends(oauth2_scheme)):
    data = utils.load_data()

    hashed_token = utils.hash_secret(web_app_token)
    for apartment_number, apartment_data in data["apartments"].items():
        for user in apartment_data["users"]:
            for token in user.get("tokens", []):
                if hashed_token == token["hash"] and token["expiration"] > int(
                    time.time()
                ):
                    return {
                        "apartment_number": apartment_number,
                        "email": user["email"],
                        "name": user["name"],
                    }

    raise HTTPException(status_code=401, detail="Unauthorized")


@app.post("/authenticate")
def authenticate(user: dict = Depends(authenticate_user)):
    return {"status": "authenticated", "user": user}


class LoginCode(BaseModel):
    login_code: str


@app.post("/exchange-code", response_model=AuthResponse)
def exchange_code(login_code: LoginCode):
    login_code_hashed = utils.hash_secret(
        login_code.login_code
    )  # todo: can we extract directly?
    data = utils.load_data()

    for apartment_number, apartment_data in data["apartments"].items():
        for user in apartment_data["users"]:
            for code in user.get("login_codes", []):
                if code["hash"] == login_code_hashed and code["expiration"] > int(
                    time.time()
                ):
                    bearer_token = token_urlsafe(16)
                    bearer_token_hashed = utils.hash_secret(bearer_token)
                    user["login_codes"].remove(code)

                    tokens_copy = user.get("tokens", []).copy()
                    for token in tokens_copy:
                        if token["expiration"] < int(time.time()):
                            user["tokens"].remove(token)

                    user_tokens = user.setdefault("tokens", [])
                    user_tokens.append(
                        {
                            "hash": bearer_token_hashed,
                            "expiration": int(time.time()) + 31536000,
                        }  # 1 year expiration
                    )
                    utils.save_data(data)
                    return {
                        "access_token": bearer_token,
                        "token_type": "bearer",
                        "user": {
                            "apartment_number": apartment_number,
                            "email": user["email"],
                            "name": user["name"],
                        },
                    }

    raise HTTPException(status_code=401, detail="Invalid or expired login code")


@app.post("/unlock")
def unlock(_: dict = Depends(authenticate_user)):
    utils.unlock_door()
    return {"message": "Door unlocked successfully"}


if __name__ == "__main__":
    port = int(os.environ.get("API_PORT", 8000))
    uvicorn.run(app, host=os.environ.get("API_HOST", "localhost"), port=port)
