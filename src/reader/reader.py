import src.utils as utils
from dotenv import load_dotenv
import os
from collections import deque
from src.db import get_all_pins, get_all_rfids
from src.reader.input_handler import read_input
from src.utils import logging
import asyncio

load_dotenv()

input_lock = asyncio.Lock()

reader_task = None
task_running = False

RFID_LENGTH = int(os.getenv("RFID_LENGTH", 10))
INPUT_MODE = os.getenv("INPUT_MODE", "standard")
INPUT_TIMEOUT = int(os.getenv("INPUT_TIMEOUT", 10))


def open_door():
    """Activate the relay to open the door."""
    logging.info("PIN or RFID correct! Activating relay.")
    asyncio.create_task(utils.unlock_door())
    logging.info("Relay deactivated.")


input_buffer = deque(maxlen=10)


def check_input(input_value):
    # todo: yes we could probably check the length of the input and if it's over the max length of a PIN

    # Check if it's a PIN
    all_pins = get_all_pins()
    for pin in all_pins:
        if utils.hash_secret(input_value, pin.salt) == pin.hashed_pin:
            logging.info("Valid PIN used")
            return True

    # If not a PIN, check if it's an RFID
    all_rfids = get_all_rfids()
    for rfid in all_rfids:
        if utils.hash_secret(input_value, rfid.salt) == rfid.hashed_uuid:
            logging.info("Valid RFID used")
            return True

    logging.warning("Invalid PIN or RFID attempted")
    return False


async def run_reader():
    global reader_status
    reader_status = "running"
    try:
        while task_running:
            print("Waiting for a complete PIN or RFID input...", flush=True)
            try:
                async with input_lock:
                    input_value = await read_input(timeout=INPUT_TIMEOUT)
                if input_value:
                    # Process the input_value
                    if (
                        check_input(input_value) is True
                    ):  # important to compare with True, not just if ... because if e.g. we change check_input to an async function and not await it properly, it will return a coroutine and not True. This bug would mean that the door would open for any input.
                        asyncio.create_task(utils.unlock_door())
                        logging.info(f"Door opened for input: {input_value}")
                    else:
                        logging.debug(f"Invalid input: {input_value}")
                else:
                    logging.info("Input timeout or no input received.")
            except asyncio.CancelledError:
                logging.info("Reader task cancelled")
                break
            except Exception as e:
                logging.error(f"Exception in run_reader: {e}")
                break
    finally:
        reader_status = "stopped"


def start_reader():
    global reader_task, task_running
    if not task_running:
        task_running = True
        loop = asyncio.get_event_loop()
        reader_task = loop.create_task(run_reader())
        logging.info("Reader started")
    else:
        logging.warning("Reader is already running")


def stop_reader():
    global task_running
    if task_running:
        task_running = False
        logging.info("Reader stop requested")
    else:
        logging.warning("Reader is not running")


def get_reader_status():
    global task_running
    return "running" if task_running else "stopped"
