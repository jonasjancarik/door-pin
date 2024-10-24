from fastapi import APIRouter, Request, status, Response, Depends
from fastapi.security import OAuth2PasswordBearer
from ..models import (
    LoginRequest,
    LoginCodeAttempt,
    AuthResponse,
    VerifyAuthResponse,
    User,
)
from ..exceptions import APIException
from ..dependencies import get_current_token, get_current_user
from ..utils import check_rate_limit, build_user_response
import src.db as db
import src.utils as utils
import os
import boto3
import logging
from botocore.exceptions import ClientError, EndpointConnectionError
import time as time_module
from secrets import token_urlsafe
import random

router = APIRouter(prefix="/auth", tags=["auth"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


@router.post("/magic-links", status_code=status.HTTP_202_ACCEPTED)
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


@router.post(
    "/verify", status_code=status.HTTP_200_OK, response_model=VerifyAuthResponse
)
def verify_authentication(
    request: Request,
    current_user: User = Depends(get_current_user),  # Add the dependency here
):
    current_token = get_current_token(request)
    new_expiration = int(time_module.time()) + 31536000  # 1 year from now
    db.extend_token_expiration(current_token, new_expiration)
    return VerifyAuthResponse(
        status="authenticated", user=build_user_response(current_user)
    )


@router.delete("/tokens/current", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    current_user: User = Depends(get_current_user),
    current_token: str = Depends(get_current_token),
):
    email = current_user.email
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


@router.post(
    "/tokens", response_model=AuthResponse, status_code=status.HTTP_201_CREATED
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
        "user": build_user_response(user),
    }
