import RPi.GPIO as GPIO
import time
import hashlib

# config
RELAY_PIN = 18
RELAY_ACTIVATION_TIME = 0.5  # seconds

# GPIO setup
GPIO.setmode(GPIO.BCM)
GPIO.setup(RELAY_PIN, GPIO.OUT)
GPIO.output(RELAY_PIN, GPIO.LOW)


def unlock_door():
    GPIO.output(RELAY_PIN, GPIO.HIGH)
    time.sleep(RELAY_ACTIVATION_TIME)
    GPIO.output(RELAY_PIN, GPIO.LOW)


def hash_secret(username, token):
    salted_token = f"{username}{token}"
    return hashlib.sha256(salted_token.encode("utf-8")).hexdigest()
