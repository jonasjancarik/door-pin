import asyncio
import logging
from evdev import InputDevice, categorize, ecodes, list_devices
import utils
import argparse

args = argparse.ArgumentParser()
args.add_argument("--debug", action="store_true", help="Enable debug mode")
args.add_argument("--timeout", type=int, default=10, help="Input timeout in seconds")
args.add_argument("--pin-length", type=int, default=4, help="PIN length")
args.add_argument("--rfid-length", type=int, default=10, help="RFID length")
args = args.parse_args()

logging.basicConfig(
    level=logging.DEBUG if args.debug else logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)


def open_door():
    """Activate the relay to open the door."""
    logging.info("PIN or RFID correct! Activating relay.")
    utils.unlock_door()
    logging.info("Relay deactivated.")


def find_keyboards():
    """Find and return a list of keyboard devices."""
    devices = [InputDevice(path) for path in list_devices()]
    keyboards = [
        device
        for device in devices
        if "keyboard" in device.name.lower() or "event" in device.path
    ]
    return keyboards


async def handle_keyboard(keyboard):
    input_pin = ""
    last_input_time = asyncio.get_event_loop().time()
    logging.info(f"Using keyboard: {keyboard.name} at {keyboard.path}")
    print("Enter PIN or scan RFID: ", end="", flush=True)

    try:
        async for event in keyboard.async_read_loop():
            current_time = asyncio.get_event_loop().time()
            if current_time - last_input_time > args.timeout:
                input_pin = ""
                logging.info("Input reset due to timeout.")
                print("\nEnter PIN or scan RFID: ", end="", flush=True)

            last_input_time = current_time

            if event.type == ecodes.EV_KEY:
                data = categorize(event)
                if data.keystate == 1:  # Key down events only
                    if isinstance(data.keycode, list):
                        key_code = data.keycode[0]
                    else:
                        key_code = data.keycode

                    if "KEY_" in key_code:
                        key = key_code.split("_")[1].replace("KP", "")
                        # check if key is an alphanumeric character
                        if key.isdigit() or key.isalpha():
                            input_pin += key
                            if args.debug:
                                print(
                                    f"\rEnter PIN or scan RFID: {input_pin}",
                                    end="",
                                    flush=True,
                                )
                            else:
                                print(
                                    f"\rEnter PIN or scan RFID: {'*' * len(input_pin)}",
                                    end="",
                                    flush=True,
                                )

                            # Check if PIN is valid
                            if len(input_pin) >= args.pin_length:
                                pin = input_pin[-args.pin_length :]

                                data = utils.load_data()

                                for apartment_number in data["apartments"]:
                                    if "pins" in data["apartments"][apartment_number]:
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
                                                    "Enter PIN or scan RFID: ",
                                                    end="",
                                                    flush=True,
                                                )

                            # Check if RFID is valid
                            if len(input_pin) >= args.rfid_length:
                                rfid_input = input_pin[-args.rfid_length :]

                                data = utils.load_data()
                                for apartment_number in data["apartments"]:
                                    if "rfids" in data["apartments"][apartment_number]:
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
                                                    "Enter PIN or scan RFID: ",
                                                    end="",
                                                    flush=True,
                                                )
                        else:
                            logging.info(
                                "Something else than a number or a letter was pressed. Input reset."
                            )
                            input_pin = ""
                            print(
                                "\nEnter PIN or scan RFID: ",
                                end="",
                                flush=True,
                            )
    except Exception as e:
        logging.error(f"Error handling keyboard {keyboard.path}: {e}")


async def main():
    keyboards = find_keyboards()
    if not keyboards:
        logging.error("No keyboards found.")
        return

    tasks = [asyncio.create_task(handle_keyboard(keyboard)) for keyboard in keyboards]
    await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())
