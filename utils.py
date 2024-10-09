import RPi.GPIO as GPIO
import time
import hashlib
from dotenv import load_dotenv
import os
import sys

load_dotenv()

# config
try:
    RELAY_PIN = int(os.getenv("RELAY_PIN", 18))
except ValueError:
    os.exit("RELAY_PIN must be an integer")

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


def hash_secret(payload=None, salt=None):
    """
    Hashes the given payload using SHA256 algorithm.

    Args:
        payload (str): The payload to be hashed.
        salt (str): The salt to be added to the payload before hashing.

    Returns:
        str: The hashed value of the payload.

    Raises:
        ValueError: If neither payload nor salt is provided.
    """
    if salt and payload:
        string_to_hash = f"{salt}{payload}"
    elif payload:
        string_to_hash = payload
    else:
        raise ValueError("At least the payload must be provided.")
    return hashlib.sha256(string_to_hash.encode("utf-8")).hexdigest()


def generate_salt():
    return os.urandom(16).hex()
