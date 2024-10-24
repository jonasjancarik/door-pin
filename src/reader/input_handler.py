import asyncio
from collections import deque
import logging
import os
from dotenv import load_dotenv

try:
    from evdev import InputDevice, categorize, ecodes, list_devices  # type: ignore
except ImportError:
    logging.error(
        "Failed to import evdev. Make sure you have the evdev library installed in production."
    )
    pass

load_dotenv()

INPUT_SOURCE = os.getenv("INPUT_SOURCE", "stdin")
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
    if INPUT_SOURCE == "stdin":
        logging.info("Reading input from stdin")
        return await read_stdin(timeout)
    else:
        logging.info("Reading input from evdev")
        try:
            # Create a queue for input events
            input_queue = asyncio.Queue()
            # Start the input reading task
            read_task = asyncio.create_task(read_evdev(timeout, input_queue))

            # Wait for either timeout or input
            try:
                result = await asyncio.wait_for(input_queue.get(), timeout=timeout)
                read_task.cancel()  # Cancel the reading task once we have input
                return result
            except asyncio.TimeoutError:
                read_task.cancel()  # Cancel the reading task on timeout
                return None
        except Exception as e:
            logging.error(f"Error in read_input: {e}")
            return None


async def read_evdev(timeout, input_queue):
    try:
        keyboards = find_keyboards()
        if not keyboards:
            logging.error("No keyboards found.")
            return None

        # Create shared buffers
        input_buffer = deque(maxlen=MAX_INPUT_LENGTH)
        t9em_input_buffer = deque(maxlen=10)

        # Create tasks for each keyboard
        keyboard_tasks = []
        for keyboard in keyboards:
            task = asyncio.create_task(
                read_keyboard_events(
                    keyboard, input_buffer, t9em_input_buffer, input_queue
                )
            )
            keyboard_tasks.append(task)

        # Wait for any keyboard task to complete or timeout
        try:
            if timeout is not None:
                await asyncio.wait_for(asyncio.gather(*keyboard_tasks), timeout=timeout)
            else:
                await asyncio.gather(*keyboard_tasks)
        except asyncio.TimeoutError:
            logging.debug("Keyboard input timeout reached")
            # Clear the buffers on timeout
            input_buffer.clear()
            t9em_input_buffer.clear()
        except asyncio.CancelledError:
            logging.debug("Keyboard tasks cancelled")
            # Also clear buffers on cancellation
            input_buffer.clear()
            t9em_input_buffer.clear()
        finally:
            # Cancel all keyboard tasks
            for task in keyboard_tasks:
                if not task.done():
                    task.cancel()
            # Wait for all tasks to complete their cancellation
            await asyncio.gather(*keyboard_tasks, return_exceptions=True)
    except Exception as e:
        logging.error(f"Error in read_evdev: {e}")
        raise


async def read_keyboard_events(device, input_buffer, t9em_input_buffer, input_queue):
    try:
        async for event in device.async_read_loop():
            if event.type == ecodes.EV_KEY:
                data = categorize(event)
                if data.keystate == 1:  # Key down events only
                    key = process_key(data.keycode)
                    if key:
                        if INPUT_SOURCE == "t9em":
                            # Handle t9em input mode
                            if key == "ENTER":
                                input_sequence = "".join(t9em_input_buffer)
                                decoded_key = decode_keypad_input(input_sequence)
                                if decoded_key:
                                    input_buffer.append(decoded_key)
                                else:
                                    input_buffer.append(input_sequence)
                                result = "".join(input_buffer)
                                await input_queue.put(result)
                                return
                            else:
                                t9em_input_buffer.append(key)
                        else:
                            if key.isdigit() or key.isalpha():
                                input_buffer.append(key)
                            elif key == "ENTER":
                                result = "".join(input_buffer)
                                await input_queue.put(result)
                                return
    except asyncio.CancelledError:
        raise
    except Exception as e:
        logging.error(f"Error reading keyboard events: {e}")
        raise


def process_key(keycode):
    if isinstance(keycode, list):
        key_code = keycode[0]
    else:
        key_code = keycode

    logging.debug(f"Processing keycode: {key_code}")

    if "KEY_" in key_code:
        return key_code.split("_")[1].replace("KP", "")
    return None


async def read_stdin(timeout=None):
    loop = asyncio.get_event_loop()
    try:
        input_value = await asyncio.wait_for(
            loop.run_in_executor(None, input, "You can enter PIN or RFID now...\n"),
            timeout=timeout,
        )
        return input_value.strip()
    except asyncio.TimeoutError:
        logging.warning("Input timeout reached.")
        return None
