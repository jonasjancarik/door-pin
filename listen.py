from evdev import InputDevice, categorize, ecodes, list_devices
import json
import sys
import utils

PIN_LENGTH = 6  # Total length including user ID
RFID_LENGTH = 10  # Adjust this as per your RFID reader's UUID length


def open_door():
    """Activate the relay to open the door."""
    print("\nPIN or RFID correct! Activating relay.")
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
    rfid_input = ""

    print("Enter User ID and PIN or scan RFID: ", end="", flush=True)
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

                                    pins_hashed = set()

                                    data = utils.load_data()
                                    for apartment_number in data["apartments"]:
                                        if (
                                            "pins"
                                            in data["apartments"][apartment_number]
                                        ):
                                            for pin in data["apartments"][
                                                apartment_number
                                            ]["pins"]:
                                                pins_hashed.add(pin["hashed_pin"])

                                    if (
                                        utils.hash_secret(salt=user_id, payload=pin)
                                        in pins_hashed
                                    ):
                                        open_door()
                                        input_pin = ""
                                        print(
                                            "Enter User ID and PIN: ",
                                            end="",
                                            flush=True,
                                        )
                                elif len(input_pin) == RFID_LENGTH:
                                    input_pin

                                    rfids_hashed = set()

                                    data = utils.load_data()
                                    for apartment_number in data["apartments"]:
                                        if (
                                            "rfids"
                                            in data["apartments"][apartment_number]
                                        ):
                                            for rfid in data["apartments"][
                                                apartment_number
                                            ]["rfids"]:
                                                rfids_hashed.add(rfid["hashed_rfid"])

                                    if (
                                        utils.hash_secret(payload=input_pin)
                                        in rfids_hashed
                                    ):
                                        open_door()
                                        input_pin = ""
                                        print(
                                            "Enter User ID and PIN: ",
                                            end="",
                                            flush=True,
                                        )
                                    else:
                                        print("\nRFID not found. Please try again.")
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
