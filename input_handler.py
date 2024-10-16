import asyncio
from collections import deque
import logging
import os
from dotenv import load_dotenv

try:
    from evdev import InputDevice, categorize, ecodes, list_devices
except ImportError:
    logging.error(
        "Failed to import evdev. Make sure you have the evdev library installed."
    )
    pass

load_dotenv()

INPUT_MODE = os.getenv("INPUT_MODE", "standard")
MAX_INPUT_LENGTH = 20  # Set a reasonable maximum length for input
PIN_LENGTH = os.getenv("PIN_LENGTH", 4)

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


def find_keyboards():
    devices = [InputDevice(path) for path in list_devices()]
    return [
        device
        for device in devices
        if "keyboard" in device.name.lower() or "event" in device.path
    ]


def decode_keypad_input(input_sequence):
    return KEY_CODES.get(input_sequence, "")


async def read_input(timeout=None):
    keyboards = find_keyboards()
    if not keyboards:
        logging.error("No keyboards found.")
        return None

    input_buffer = deque(maxlen=MAX_INPUT_LENGTH)
    special_input_buffer = deque(maxlen=10)
    start_time = asyncio.get_event_loop().time()

    # Create a list to store the tasks for each keyboard
    tasks = []

    # Create a coroutine for each keyboard
    for keyboard in keyboards:
        tasks.append(
            asyncio.create_task(
                read_events(
                    keyboard, input_buffer, special_input_buffer, start_time, timeout
                )
            )
        )

    # Wait for any of the tasks to complete
    done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)

    # Cancel all pending tasks
    for task in pending:
        task.cancel()

    # Return the input buffer
    return "".join(input_buffer) if input_buffer else None


async def read_events(device, input_buffer, special_input_buffer, start_time, timeout):
    try:
        async for event in device.async_read_loop():
            if event.type == ecodes.EV_KEY:
                data = categorize(event)
                if data.keystate == 1:  # Key down events only
                    current_time = asyncio.get_event_loop().time()
                    key = process_key(data.keycode)
                    if key:
                        if timeout and (current_time - start_time) > timeout:
                            logging.warning(
                                "Input timeout reached. Resetting input buffer."
                            )
                            input_buffer.clear()
                            special_input_buffer.clear()
                        start_time = current_time  # Reset start time on keypress
                        logging.debug(f"Key pressed: {key}")
                        if INPUT_MODE == "special":
                            # Special handling logic
                            if key == "ENTER":
                                input_sequence = "".join(special_input_buffer)
                                # try decoding the input
                                decoded_key = decode_keypad_input(input_sequence)
                                if decoded_key:
                                    input_buffer.append(decoded_key)
                                else:
                                    # we couldn't decode the input, meaning it's probably a RFID
                                    input_buffer.append(input_sequence)
                                special_input_buffer.clear()
                                if not decoded_key:
                                    return  # Return after processing ENTER key
                                elif len(input_buffer) == PIN_LENGTH:
                                    return "".join(input_buffer)
                            else:
                                special_input_buffer.append(key)
                        else:
                            if key and (key.isdigit() or key.isalpha()):
                                input_buffer.append(key)
                            if key == "ENTER":
                                return  # Return when ENTER key is pressed
    except Exception as e:
        logging.error(f"Error reading events from device {device.path}: {e}")


def process_key(keycode):
    if isinstance(keycode, list):
        key_code = keycode[0]
    else:
        key_code = keycode

    logging.debug(f"Processing keycode: {key_code}")

    if "KEY_" in key_code:
        return key_code.split("_")[1].replace("KP", "")
    return None
