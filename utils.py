import RPi.GPIO as GPIO
import time
import bcrypt
from dotenv import load_dotenv
import os
import sys

load_dotenv()

# config
try:
    RELAY_PIN = int(os.getenv("RELAY_PIN", 18))
except ValueError:
    sys.exit("RELAY_PIN must be an integer")

RELAY_ACTIVATION_TIME = int(os.getenv("RELAY_ACTIVATION_TIME", 5))  # seconds

if os.getenv("RELAY_ACTIVE_STATE", "HIGH") not in {"HIGH", "LOW"}:
    raise ValueError("RELAY_ACTIVE_STATE must be either HIGH or LOW")

RELAY_ACTIVE_STATE = (
    GPIO.HIGH if os.getenv("RELAY_ACTIVE_STATE") == "HIGH" else GPIO.LOW
)

# GPIO setup
try:
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(RELAY_PIN, GPIO.OUT)
    GPIO.output(RELAY_PIN, not RELAY_ACTIVE_STATE)  # deactivate first
    GPIO.cleanup()  # cleanup to avoid issues with previous runs
except Exception as e:
    print(f"Error setting up GPIO: {e}")
    if "Cannot determine SOC peripheral base address" in str(e):
        sys.exit(
            "rpi-gpio is not supported on this hardware. If you are on a Raspberry PI 5, run pip uninstall rpi-gpio; pip install rpi-lgpio"
        )


def unlock_door(duration=RELAY_ACTIVATION_TIME):
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(RELAY_PIN, GPIO.OUT)
    GPIO.output(RELAY_PIN, RELAY_ACTIVE_STATE)
    time.sleep(duration)
    GPIO.output(RELAY_PIN, not RELAY_ACTIVE_STATE)
    GPIO.cleanup()


def hash_secret(payload, salt=None):
    """
    Hashes the given payload using bcrypt.

    Args:
        payload (str): The payload to be hashed (e.g., password).
        salt (bytes, optional): The salt to be used. If not provided, a new salt will be generated.

    Returns:
        str: The bcrypt hash of the payload as a string.

    Raises:
        ValueError: If payload is not provided.
    """
    if not payload:
        raise ValueError("Payload must be provided.")

    if not salt:
        salt = bcrypt.gensalt()

    hashed = bcrypt.hashpw(payload.encode("utf-8"), salt)
    return hashed.decode("utf-8")  # Return as string


def verify_secret(payload, hashed):
    """
    Verifies a payload against a bcrypt hash.

    Args:
        payload (str): The payload to verify (e.g., password attempt).
        hashed (str): The bcrypt hash to check against.

    Returns:
        bool: True if the payload matches the hash, False otherwise.
    """
    return bcrypt.checkpw(payload.encode("utf-8"), hashed.encode("utf-8"))
