import RPi.GPIO as GPIO
import time
import hashlib
import pexpect
import json

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


class BluetoothctlError(Exception):
    """This exception is raised when bluetoothctl fails to start or execute a command."""

    pass


class Bluetoothctl:
    """A wrapper for managing bluetooth actions with bluetoothctl."""

    def __init__(self):
        try:
            self.child = pexpect.spawn("bluetoothctl", echo=False)
            # self.child.expect("#", timeout=5)
        except (pexpect.EOF, pexpect.TIMEOUT) as e:
            raise BluetoothctlError("Error starting bluetoothctl: " + str(e))

    def get_output(self, command, pause=1):
        """Send a command to bluetoothctl prompt and return the output."""
        self.child.sendline(command)
        time.sleep(pause)
        self.child.expect("#", timeout=5)
        return self.child.before.decode().split("\r\n")

    def start_scan(self, scan_duration=10):
        """Start scanning for nearby devices for a specified duration."""
        print("Starting to scan for devices...")
        self.get_output("scan on", 1)
        print(f"Scanning for {scan_duration} seconds...")
        time.sleep(scan_duration)
        self.get_output("scan off", 1)
        print("Scan completed.")

    def list_devices(self):
        """List available devices."""
        print("Getting available devices...")
        output = self.get_output("devices")
        devices = []
        for line in output:
            line = line.strip()
            if "Device" in line:
                parts = line.split(" ", 2)
                if len(parts) >= 3:
                    devices.append((parts[1], parts[2]))
        return devices

    def list_paired_devices(self, mac_only=True):
        """List paired devices."""
        print("Getting paired devices...")
        output = self.get_output("paired-devices")
        devices = []
        for line in output:
            if "Device" in line:
                if mac_only:
                    devices.append(line.split("Device ")[1].split(" ")[0])
                else:
                    devices.append(line.split("Device ")[1])
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
        with open("approved_devices.json") as f:
            return json.load(f)
    except FileNotFoundError:
        return []
