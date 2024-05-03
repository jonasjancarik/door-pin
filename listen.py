import time
import hashlib
import RPi.GPIO as GPIO
from evdev import InputDevice, categorize, ecodes

# Configuration Constants
RELAY_PIN = 18
RELAY_ACTIVATION_TIME = 5  # seconds
USER_PIN_LENGTH = 6
TIMEOUT_DURATION = 30  # seconds
KEYBOARD_PATH = "/dev/input/event0"  # Will be used if there are multiple keyboards

# GPIO setup
GPIO.setmode(GPIO.BCM)
GPIO.setup(RELAY_PIN, GPIO.OUT)
GPIO.output(RELAY_PIN, GPIO.LOW)

# Load hashed PINs from a file
user_hashes = {}
with open("hashed_pins.txt", "r") as file:
    for line in file:
        user_id, hashed_pin = line.strip().split(":")
        user_hashes[user_id] = hashed_pin


def hash_pin(user_id, pin):
    """Hash a PIN using SHA-256 with user ID as salt and return the hexadecimal string."""
    salted_pin = user_id + pin
    hasher = hashlib.sha256()
    hasher.update(salted_pin.encode("utf-8"))
    return hasher.hexdigest()


def open_door():
    """Activate the relay to open the door."""
    print("\nPIN correct! Activating relay.")
    GPIO.output(RELAY_PIN, GPIO.HIGH)
    time.sleep(RELAY_ACTIVATION_TIME)
    GPIO.output(RELAY_PIN, GPIO.LOW)
    print("Relay deactivated.")


def find_keyboard():
    """Find and return a keyboard device."""
    from evdev import list_devices

    devices = [InputDevice(path) for path in list_devices()]
    if len(devices) == 1:
        return devices[0]
    for device in devices:
        if device.path == KEYBOARD_PATH:
            return device
    if len(devices) > 1:
        print("Multiple keyboards found. Using the first one.")
        return devices[0]
    return None


def main():
    keyboard = find_keyboard()
    if not keyboard:
        print("Keyboard not found.")
        return

    print(f"Using keyboard: {keyboard.name} at {keyboard.path}")
    input_pin = ""
    last_input_time = time.time()

    print("Enter User ID and PIN (6 digits): ", end="", flush=True)
    while True:
        for event in keyboard.read_loop():
            if event.type == ecodes.EV_KEY:
                data = categorize(event)
                if data.keystate == 1:  # Down events only
                    if isinstance(data.keycode, list):
                        key_code = data.keycode[0]
                    else:
                        key_code = data.keycode

                    # print(f"Detected key code: {key_code}")  # Debug print

                    if "KEY_" in key_code:
                        key = key_code.split("_")[1].replace("KP", "")
                        if key.isdigit() and len(input_pin) < USER_PIN_LENGTH:
                            input_pin += key
                            print(key, end="", flush=True)
                            last_input_time = time.time()
                        else:
                            print(
                                "A non-digit key was pressed. PIN entry has been reset."
                            )
                            input_pin = ""  # clear input on any other key

                        if len(input_pin) == USER_PIN_LENGTH:
                            user_id, pin = input_pin[:2], input_pin[2:]
                            if hash_pin(user_id, pin) == user_hashes.get(user_id, ""):
                                open_door()
                            else:
                                print("\nIncorrect PIN or User ID.")
                            input_pin = ""
                            print(
                                "\nEnter User ID and PIN (6 digits): ",
                                end="",
                                flush=True,
                            )

                        if time.time() - last_input_time > TIMEOUT_DURATION:
                            print(
                                "\nNo input for 30 seconds. PIN entry has been reset."
                            )
                            input_pin = ""
                            print(
                                "Enter User ID and PIN (6 digits): ", end="", flush=True
                            )


if __name__ == "__main__":
    main()
