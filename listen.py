import asyncio
import logging
import utils
import argparse
from dotenv import load_dotenv
import os
import db
from collections import deque
import getpass

# Try to import evdev, but don't fail if it's not available
try:
    from evdev import InputDevice, categorize, ecodes, list_devices

    EVDEV_AVAILABLE = True
except ImportError:
    EVDEV_AVAILABLE = False

load_dotenv()

KEY_CODES = {
    "0225": "1",
    "0210": "2",
    "0195": "3",
    "0180": "4",
    "0165": "5",
    "0150": "6",
    "0135": "7",
    "0120": "8",
    "0105": "9",
    "0240": "0",
    "0090": "*",
    "0075": "#",
}


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--timeout", type=int, default=10, help="Input timeout in seconds"
    )
    parser.add_argument("--pin-length", type=int, default=4, help="PIN length")
    parser.add_argument(
        "--rfid-length", type=int, help="RFID length (overrides RFID_LENGTH env var)"
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default=os.getenv("LOG_LEVEL", "INFO"),
        help="Set the logging level (default: INFO)",
    )
    parser.add_argument(
        "--input-mode",
        choices=["standard", "special"],
        help="Input mode: 'standard' for regular input, 'special' for key code input",
    )
    return parser.parse_args()


args = parse_args()
RFID_LENGTH = args.rfid_length or int(os.getenv("RFID_LENGTH", 10))
INPUT_MODE = args.input_mode or os.getenv("INPUT_MODE", "standard")

logging.basicConfig(
    level=getattr(logging, args.log_level),
    format="%(asctime)s - %(levelname)s - %(message)s",
)


def open_door():
    logging.info("PIN or RFID correct! Activating relay.")
    utils.unlock_door()
    logging.info("Relay deactivated.")


def check_input(input_pin):
    if len(input_pin) == args.pin_length:
        if any(
            utils.hash_secret(salt=entry.salt, payload=input_pin) == entry.hashed_pin
            for entry in db.get_all_pins()
        ):
            return True

    if len(input_pin) == RFID_LENGTH:
        if any(
            utils.hash_secret(salt=entry.salt, payload=input_pin) == entry.hashed_uuid
            for entry in db.get_all_rfids()
        ):
            return True

    return False


async def handle_input(get_key, device_info=""):
    pin_buffer = deque(maxlen=args.pin_length)
    last_input_time = asyncio.get_event_loop().time()
    if device_info:
        logging.info(f"Using input device: {device_info}")
    print("Enter PIN or scan RFID: ", end="", flush=True)

    while True:
        current_time = asyncio.get_event_loop().time()
        if current_time - last_input_time > args.timeout:
            pin_buffer.clear()
            logging.info("Input reset due to timeout.")
            print("\nEnter PIN or scan RFID: ", end="", flush=True)

        key = await get_key()
        last_input_time = asyncio.get_event_loop().time()

        if INPUT_MODE == "special":
            if key.strip():  # Ignore empty lines
                if len(key) > 4:  # RFID card input
                    input_pin = key.strip()
                    if check_input(input_pin):
                        open_door()
                    pin_buffer.clear()
                else:  # PIN input
                    digit = KEY_CODES.get(key.strip())
                    if digit:
                        pin_buffer.append(digit)
                        input_pin = "".join(pin_buffer)
                        if len(pin_buffer) == args.pin_length and check_input(
                            input_pin
                        ):
                            open_door()
                            pin_buffer.clear()
        else:  # standard mode
            if key.isalnum():
                pin_buffer.append(key)
                input_pin = "".join(pin_buffer)
                if len(input_pin) >= args.pin_length and check_input(input_pin):
                    open_door()
                    pin_buffer.clear()

        logging.debug(f"Current input: {''.join(pin_buffer)}")

        if len(pin_buffer) == 0:
            print("\nEnter PIN or scan RFID: ", end="", flush=True)


async def get_standard_input():
    return await asyncio.get_event_loop().run_in_executor(None, getpass.getpass, "")


async def get_evdev_input(device):
    async for event in device.async_read_loop():
        if event.type == ecodes.EV_KEY and categorize(event).keystate == 1:
            key_code = categorize(event).keycode
            key = (
                key_code.split("_")[1].replace("KP", "")
                if isinstance(key_code, str)
                else key_code[0].split("_")[1].replace("KP", "")
            )
            return key
    return ""


async def main():
    if EVDEV_AVAILABLE:
        keyboards = [
            device
            for device in map(InputDevice, list_devices())
            if "keyboard" in device.name.lower() or "event" in device.path
        ]

        if keyboards:
            await asyncio.gather(
                *(
                    handle_input(
                        lambda d=dev: get_evdev_input(d), f"{dev.name} at {dev.path}"
                    )
                    for dev in keyboards
                )
            )
            return

        logging.warning("No evdev keyboards found. Falling back to standard input.")
    else:
        logging.info("Evdev not available. Using standard input for keyboard handling.")

    await handle_input(get_standard_input)


if __name__ == "__main__":
    asyncio.run(main())
