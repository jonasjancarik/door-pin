from collections import defaultdict
import time
from fastapi import HTTPException
import hashlib
from src.db import APIKey

rate_limit = defaultdict(list)
MAX_ATTEMPTS = 5
RATE_LIMIT_DURATION = 60  # 1 minute


def verify_api_key(db, api_key: str):
    """
    Verify an API key against the database.

    Args:
        db: SQLAlchemy database session
        api_key: The API key to verify

    Returns:
        APIKey object if valid, None if invalid
    """
    if not api_key:
        return None

    # Hash the full API key
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()

    # Query the database for a matching API key
    api_key_obj = (
        db.query(APIKey)
        .filter(
            APIKey.key_hash == key_hash,
            APIKey.is_active,
        )
        .first()
    )

    return api_key_obj


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


def apartment_return_format(apartment):
    return {
        "id": apartment.id,
        "number": apartment.number,
        "description": apartment.description,
    }


def build_user_response(user):
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email if user.email else None,
        "apartment": apartment_return_format(user.apartment)
        if user.apartment
        else None,
        "role": user.role,
    }


# Include other utility functions here
