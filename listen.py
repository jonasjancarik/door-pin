from evdev import InputDevice, categorize, ecodes, list_devices
import json
import sys
import utils

PIN_LENGTH = 6  # Total length including user ID

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


def find_keyboards():
    """Find and return a list of keyboard devices."""
    devices = [InputDevice(path) for path in list_devices()]
    keyboards = [
        device
        for device in devices
        if "keyboard" in device.name.lower() or "event" in device.path
    ]
    return keyboards


def main():
    keyboards = find_keyboards()
    if not keyboards:
        print("No keyboards found.")
        return

    for keyboard in keyboards:
        print(f"Using keyboard: {keyboard.name} at {keyboard.path}")

    input_pin = ""

    print("Enter User ID and PIN: ", end="", flush=True)
    while True:
        for keyboard in keyboards:
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
                                input_pin = input_pin[-PIN_LENGTH:]
                                print(
                                    f"\rEnter User ID and PIN: {input_pin}",
                                    end="",
                                    flush=True,
                                )

                                if len(input_pin) == PIN_LENGTH:
                                    user_id, pin = input_pin[:2], input_pin[2:]
                                    user = users.get(user_id)
                                    if user:
                                        user_pin_hashes = [
                                            x["hashed_pin"] for x in user
                                        ]
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
