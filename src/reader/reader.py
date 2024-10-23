import src.utils as utils
from dotenv import load_dotenv
import os
from collections import deque
from src.db import get_all_pins, get_all_rfids
from src.reader.input_handler import read_input
from src.utils import logging
from src.door_manager import door_manager
import asyncio

load_dotenv()

input_queue = asyncio.Queue()
reader_status = "stopped"
task_running = False
reader_task = None


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


async def input_reader():
    """Continuously reads input and puts it into the queue"""
    while task_running:
        try:
            input_value = await read_input(timeout=None)  # No timeout here
            if input_value:
                await input_queue.put(input_value)
        except Exception as e:
            logging.error(f"Error in input reader: {e}")
            await asyncio.sleep(1)  # Prevent tight loop on error


async def input_processor():
    """Processes input from the queue"""
    while task_running:
        # print("Waiting for a complete PIN or RFID input...", flush=True)
        try:
            # Use a timeout here to allow checking task_running periodically
            input_value = await asyncio.wait_for(input_queue.get(), timeout=1)
            if input_value:
                if check_input(input_value) is True:
                    await door_manager.unlock(
                        utils.unlock_door, utils.RELAY_ACTIVATION_TIME
                    )
                else:
                    logging.debug(f"Invalid input: {input_value}")
        except asyncio.TimeoutError:
            continue  # Just continue if no input received
        except Exception as e:
            logging.error(f"Error in input processor: {e}")


def start_reader():
    global reader_task, task_running, reader_status
    if not task_running:
        task_running = True
        reader_status = "running"
        loop = asyncio.get_event_loop()
        # Create separate tasks for reader and processor
        reader_task_1 = loop.create_task(input_reader())
        reader_task_2 = loop.create_task(input_processor())
        # Store both tasks
        reader_task = asyncio.gather(reader_task_1, reader_task_2)
        logging.info("Reader started")
    else:
        logging.warning("Reader is already running")


def stop_reader():
    global task_running, reader_status, reader_task
    if task_running:
        task_running = False
        reader_status = "stopped"
        if reader_task:
            reader_task.cancel()
        logging.info("Reader stop requested")
    else:
        logging.warning("Reader is not running")


def get_reader_status():
    """Returns the current status of the reader ('running' or 'stopped')"""
    return reader_status


async def read_single_input(timeout):
    """For one-off input reading (like RFID registration)"""
    try:
        return await asyncio.wait_for(read_input(timeout=timeout), timeout=timeout)
    except asyncio.TimeoutError:
        return None
