import asyncio
import logging
import utils
import argparse
from dotenv import load_dotenv
import os
from collections import deque
from db import get_all_pins, get_all_rfids
from input_handler import read_input

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

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", logging.INFO),
    format="%(asctime)s - %(levelname)s - %(message)s",
)


def open_door():
    """Activate the relay to open the door."""
    logging.info("PIN or RFID correct! Activating relay.")
    utils.unlock_door()
    logging.info("Relay deactivated.")


input_buffer = deque(maxlen=10)


def check_pin(input_value):
    # Check if it's a PIN
    all_pins = get_all_pins()
    for pin in all_pins:
        if utils.verify_secret(input_value, pin.hashed_pin):
            logging.info("Valid PIN used")
            return True

    # If not a PIN, check if it's an RFID
    all_rfids = get_all_rfids()
    for rfid in all_rfids:
        if utils.verify_secret(input_value, rfid.hashed_uuid):
            logging.info("Valid RFID used")
            return True

    logging.warning("Invalid PIN or RFID attempted")
    return False


async def main():
    while True:
        print("Waiting for a complete PIN or RFID input...", flush=True)

        input_value = await read_input(timeout=args.timeout)

        if input_value:
            if os.getenv("DEBUG"):
                print(f"Input received: {input_value}")
            else:
                print("Input received...", flush=True)
            if check_pin(input_value):
                open_door()
            else:
                logging.debug(f"Invalid input: {input_value}")
        else:
            logging.info("Input timeout or no input received.")


if __name__ == "__main__":
    asyncio.run(main())
