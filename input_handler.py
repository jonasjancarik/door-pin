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

    for keyboard in keyboards:
        async for event in keyboard.async_read_loop():
            if timeout and (asyncio.get_event_loop().time() - start_time) > timeout:
                logging.warning("Input timeout reached.")
                return "".join(input_buffer) if input_buffer else None

            if event.type == ecodes.EV_KEY:
                data = categorize(event)
                if data.keystate == 1:  # Key down events only
                    key = process_key(data.keycode)

                    if INPUT_MODE == "special":
                        if key == "ENTER":
                            input_sequence = "".join(special_input_buffer)
                            decoded_key = decode_keypad_input(input_sequence)
                            if decoded_key:
                                input_buffer.append(decoded_key)
                            special_input_buffer.clear()
                        else:
                            special_input_buffer.append(key)
                    else:
                        if key and (key.isdigit() or key.isalpha()):
                            input_buffer.append(key)

                    if key == "ENTER":
                        return "".join(input_buffer)

    return "".join(input_buffer) if input_buffer else None


def process_key(keycode):
    if isinstance(keycode, list):
        key_code = keycode[0]
    else:
        key_code = keycode

    if "KEY_" in key_code:
        return key_code.split("_")[1].replace("KP", "")
    return None
