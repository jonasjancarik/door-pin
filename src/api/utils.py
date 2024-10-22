from collections import defaultdict
import time
from fastapi import HTTPException

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


def apartment_return_format(apartment):
    return {
        "id": apartment.id,
        "number": apartment.number,
        "description": apartment.description,
    }


def user_return_format(user):
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "apartment": apartment_return_format(user.apartment),
        "role": user.role,
    }


# Include other utility functions here
