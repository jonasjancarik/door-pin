from evdev import InputDevice, categorize, ecodes, list_devices
import utils

PIN_LENGTH = 4  # Changing this would require changing web-app.py too
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
                                print(
                                    f"\rEnter User ID and PIN or scan RFID: {input_pin}",
                                    end="",
                                    flush=True,
                                )

                                # Check if PIN is valid
                                if len(input_pin) >= PIN_LENGTH:
                                    pin = input_pin[-PIN_LENGTH:]

                                    data = utils.load_data()

                                    for apartment_number in data["apartments"]:
                                        if (
                                            "pins"
                                            in data["apartments"][apartment_number]
                                        ):
                                            for pin_entry in data["apartments"][
                                                apartment_number
                                            ]["pins"]:
                                                salt = pin_entry["salt"]
                                                if (
                                                    utils.hash_secret(
                                                        salt=salt, payload=pin
                                                    )
                                                    == pin_entry["hashed_pin"]
                                                ):
                                                    open_door()
                                                    input_pin = ""
                                                    print(
                                                        "Enter User ID and PIN or scan RFID: ",
                                                        end="",
                                                        flush=True,
                                                    )

                                # Check if RFID is valid
                                if len(input_pin) >= RFID_LENGTH:
                                    rfid_input = input_pin[-RFID_LENGTH:]

                                    data = utils.load_data()
                                    for apartment_number in data["apartments"]:
                                        if (
                                            "rfids"
                                            in data["apartments"][apartment_number]
                                        ):
                                            for rfid in data["apartments"][
                                                apartment_number
                                            ]["rfids"]:
                                                if (
                                                    utils.hash_secret(
                                                        salt=rfid["salt"],
                                                        payload=rfid_input,
                                                    )
                                                    == rfid["hashed_rfid"]
                                                ):
                                                    open_door()
                                                    input_pin = ""
                                                    print(
                                                        "Enter User ID and PIN or scan RFID: ",
                                                        end="",
                                                        flush=True,
                                                    )
                            else:
                                print("\nA non-digit key was pressed. Input reset.")
                                input_pin = ""
                                print(
                                    "Enter User ID and PIN or scan RFID: ",
                                    end="",
                                    flush=True,
                                )


if __name__ == "__main__":
    main()
