import asyncio
import logging
import utils
import argparse
from dotenv import load_dotenv
import os
from collections import deque
import db
from input_handler import read_input

# Try to import evdev, but don't fail if it's not available
try:
    from evdev import InputDevice, categorize, ecodes, list_devices

    EVDEV_AVAILABLE = True
except ImportError:
    EVDEV_AVAILABLE = False

load_dotenv()


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--timeout", type=int, default=10, help="Input timeout in seconds"
    )
    parser.add_argument("--pin-length", type=int, default=4, help="PIN length")
    parser.add_argument(
        "--rfid-length",
        type=int,
        help="RFID length (overrides RFID_LENGTH env var). Defaults to 10 even without the env var.",
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug output")
    return parser.parse_args()


args = parse_args()
RFID_LENGTH = args.rfid_length or int(os.getenv("RFID_LENGTH", 10))
INPUT_MODE = os.getenv("INPUT_MODE", "standard")

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

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", logging.INFO),
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


input_buffer = deque(maxlen=10)


async def main():
    while True:
        print("Enter PIN or scan RFID: ", end="", flush=True)
        input_value = await read_input(timeout=args.timeout)

        if input_value:
            if len(input_value) == args.pin_length:
                if check_pin(input_value):
                    open_door()
            elif len(input_value) >= RFID_LENGTH:
                if check_rfid(input_value):
                    open_door()
            else:
                logging.debug(f"Input sequence too short: {input_value}")
        else:
            logging.info("Input timeout or no input received.")


if __name__ == "__main__":
    asyncio.run(main())
