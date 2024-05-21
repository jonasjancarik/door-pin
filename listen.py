from evdev import InputDevice, categorize, ecodes
import json
import sys
import utils

PIN_LENGTH = 6  # Total length including user ID
KEYBOARD_PATH = "/dev/input/event0"

# Load hashed PINs from a json file
try:
    with open("pins.json", "r") as file:
        users = json.load(file)
except FileNotFoundError:
    sys.exit('No "pins.json" file found. No PINs loaded.')


def open_door():
    """Activate the relay to open the door."""
    print("\nPIN correct! Activating relay.")
    utils.unlock_door()
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

    print("Enter User ID and PIN: ", end="", flush=True)
    while True:
        for event in keyboard.read_loop():
            if event.type == ecodes.EV_KEY:
                data = categorize(event)
                if data.keystate == 1:  # Key down events only
                    if isinstance(data.keycode, list):
                        key_code = data.keycode[0]
                    else:
                        key_code = data.keycode

                    if "KEY_" in key_code:
                        key = key_code.split("_")[1].replace("KP", "")
                        if key.isdigit():
                            input_pin += key
                            # print(key, end="", flush=True)
                            # Keep only the last 6 digits
                            input_pin = input_pin[-PIN_LENGTH:]
                            print(
                                f"\rEnter User ID and PIN: {input_pin}",
                                end="",
                                flush=True,
                            )

                            if len(input_pin) == PIN_LENGTH:
                                user_id, pin = input_pin[:2], input_pin[2:]
                                # get user's pin hashes
                                user = users.get(user_id)
                                if user:
                                    user_pin_hashes = [x["hashed_pin"] for x in user]
                                    if (
                                        utils.hash_secret(salt=user_id, payload=pin)
                                        in user_pin_hashes
                                    ):
                                        open_door()
                                        input_pin = ""
                                        print(
                                            "Enter User ID and PIN: ",
                                            end="",
                                            flush=True,
                                        )
                        else:
                            print(
                                "\nA non-digit key was pressed. Please only enter digits."
                            )
                            input_pin = ""
                            print("Enter User ID and PIN: ", end="", flush=True)


if __name__ == "__main__":
    main()
