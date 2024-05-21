import RPi.GPIO as GPIO
import time
import hashlib
import pexpect
import json
from dotenv import load_dotenv
import os

load_dotenv()

# config
try:
    RELAY_PIN = int(os.getenv("RELAY_PIN", 18))
except ValueError:
    os.exit("RELAY_PIN must be an integer")
RELAY_ACTIVATION_TIME = 0.5  # seconds

if os.getenv("RELAY_ACTIVE_STATE", "HIGH") not in {"HIGH", "LOW"}:
    raise ValueError("RELAY_ACTIVE_STATE must be either HIGH or LOW")

RELAY_ACTIVE_STATE = (
    GPIO.HIGH if os.getenv("RELAY_ACTIVE_STATE") == "HIGH" else GPIO.LOW
)

# GPIO setup
GPIO.setmode(GPIO.BCM)
GPIO.setup(RELAY_PIN, GPIO.OUT)
GPIO.output(RELAY_PIN, not RELAY_ACTIVE_STATE)  # deactivate first
GPIO.cleanup()  # cleanup to avoid issues with previous runs


def unlock_door():
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(RELAY_PIN, GPIO.OUT)
    GPIO.output(RELAY_PIN, RELAY_ACTIVE_STATE)
    time.sleep(RELAY_ACTIVATION_TIME)
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


class BluetoothctlError(Exception):
    """This exception is raised when bluetoothctl fails to start or execute a command."""

    pass


class Bluetoothctl:
    """A wrapper for managing bluetooth actions with bluetoothctl."""

    def __init__(self):
        try:
            self.child = pexpect.spawn("bluetoothctl", echo=False)
            # self.child.expect(r"\[bluetooth\]#", timeout=10)  # todo: fix expect
        except (pexpect.EOF, pexpect.TIMEOUT) as e:
            raise BluetoothctlError("Error starting bluetoothctl: " + str(e))
        except Exception as e:  # todo - this is meant only for local development without bluetoothctl, find a better solution
            print(e)

    def get_output(self, command, pause=1):
        """Send a command to bluetoothctl prompt and return the output."""
        self.child.sendline(command)
        time.sleep(pause)
        self.child.expect("#", timeout=5)
        return self.child.before.decode().split("\r\n")

    def scan(self, scan_duration=10):
        """Start scanning for nearby devices for a specified duration."""
        print("Starting to scan for devices...")
        self.get_output("scan on", 1)
        print(f"Scanning for {scan_duration} seconds...")
        time.sleep(scan_duration)
        output = self.get_output("scan off", 1)
        print("Scan completed.")
        return output

    def list_available_devices(self, scan_duration=10):
        """List available devices by scanning and filtering output."""
        print("Scanning for available devices...")
        scan_output = self.scan(scan_duration)
        devices = []
        for line in scan_output:
            line = line.strip()
            if "Device" in line and ("NEW" in line or "CHG" in line):
                parts = line.split("Device ")[1].split(" ")
                devices.append((parts[0], " ".join(parts[1:])))
        print(f"Found {len(devices)} nearby devices.")
        return devices

    def list_paired_devices(self, scan_duration=10):
        """List paired devices."""
        output = self.get_output("paired-devices", 1)
        devices = []
        for line in output:
            line = line.strip()
            if "Device" in line:
                parts = line.split("Device ")[1].split(" ")
                devices.append({"mac": parts[0], "name": " ".join(parts[1:])})
        return devices

    def pair_device(self, mac_address):
        """Pair with a device using its MAC address."""
        print(f"Trying to pair with {mac_address}...")
        output = self.get_output(
            f"pair {mac_address}"
        )  # todo - we should display the pairing code to confirm

        answer = ""

        while answer not in {"yes", "no"}:
            answer = input("Confirm pairing? (yes/no)")
            if answer in {"yes", "no"}:
                output = self.get_output(answer)
            else:
                print("Answer must be yes or no.")

        for line in output:
            if "Failed" in line:
                return False
            if "Pairing successful" in line:
                return True

        return False

    def remove_device(self, mac_address):
        """Remove a paired device."""
        print(f"Removing {mac_address}...")
        output = self.get_output(f"remove {mac_address}", 3)
        return "Device has been removed" in output


def get_approved_devices():
    try:
        with open("devices.json") as f:
            return json.load(f)
    except FileNotFoundError:
        return []


def load_data():
    try:
        with open("data.json", "r") as file:
            return json.load(file)
    except FileNotFoundError:
        return {"apartments": {}}


def save_data(data):
    with open("data.json", "w") as file:
        json.dump(data, file, indent=4)
