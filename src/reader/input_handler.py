import asyncio
from collections import deque
from src.logger import logger
import os
from dotenv import load_dotenv

try:
    from evdev import InputDevice, categorize, ecodes, list_devices  # type: ignore
except ImportError:
    logger.error(
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


async def read_input():
    if INPUT_SOURCE == "stdin":
        logger.info("Reading input from stdin")
        return await read_stdin()
    else:
        logger.info("Reading input from evdev")
        try:
            input_queue = asyncio.Queue()
            read_task = asyncio.create_task(read_evdev(input_queue))

            try:
                result = await input_queue.get()
                read_task.cancel()
                try:
                    await read_task
                except asyncio.CancelledError:
                    pass
                return result
            except Exception as e:
                read_task.cancel()
                try:
                    await read_task
                except asyncio.CancelledError:
                    pass
                logger.error(f"Error in read_input: {e}")
                return None
        except Exception as e:
            logger.error(f"Error in read_input: {e}")
            return None


async def read_stdin():
    timeout = int(os.getenv("INPUT_TIMEOUT", 10))
    loop = asyncio.get_running_loop()
    try:
        input_value = await asyncio.wait_for(
            loop.run_in_executor(None, input, "You can enter PIN or RFID now...\n"),
            timeout=timeout,
        )
        return input_value.strip()
    except asyncio.TimeoutError:
        logger.warning("Input timeout reached.")
        return None


async def read_evdev(input_queue):
    try:
        keyboards = find_keyboards()
        if not keyboards:
            logger.error("No keyboards found.")
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

        # Wait for any keyboard task to complete
        try:
            await asyncio.gather(*keyboard_tasks)
        except asyncio.CancelledError:
            logger.debug("Keyboard tasks cancelled")
            # Clear buffers on cancellation
            input_buffer.clear()
            t9em_input_buffer.clear()
        finally:
            # Cancel all keyboard tasks
            for task in keyboard_tasks:
                if not task.done():
                    task.cancel()
            # Wait for all tasks to complete their cancellation
            try:
                await asyncio.gather(*keyboard_tasks, return_exceptions=True)
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.error(f"Error in read_evdev: {e}")
                raise
    except Exception as e:
        logger.error(f"Error in read_evdev: {e}")
        raise


async def read_keyboard_events(device, input_buffer, t9em_input_buffer, input_queue):
    timeout = int(os.getenv("INPUT_TIMEOUT", 10))
    try:
        first_key_received = False
        start_time = None

        async for event in device.async_read_loop():
            if event.type == ecodes.EV_KEY:
                data = categorize(event)
                if data.keystate == 1:  # Key down events only
                    if not first_key_received:
                        first_key_received = True
                        start_time = asyncio.get_running_loop().time()

                    key = process_key(data.keycode)
                    if key:
                        if start_time is not None:
                            if asyncio.get_running_loop().time() - start_time > timeout:
                                logger.debug(
                                    "Timeout reached after first keypress, clearing buffers"
                                )
                                input_buffer.clear()
                                t9em_input_buffer.clear()
                                first_key_received = False
                                start_time = None

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
                                input_buffer.clear()
                                t9em_input_buffer.clear()
                                first_key_received = False
                                start_time = None
                            else:
                                t9em_input_buffer.append(key)
                        else:
                            if key.isdigit() or (key.isalpha() and key != "ENTER"):
                                input_buffer.append(key)
                            elif key == "ENTER":
                                result = "".join(input_buffer)
                                await input_queue.put(result)
                                input_buffer.clear()
                                first_key_received = False
                                start_time = None

    except asyncio.CancelledError:
        pass  # This is expected when the task is cancelled
    except Exception as e:
        logger.error(f"Error reading keyboard events: {e}")
        raise


def process_key(keycode):
    if isinstance(keycode, list):
        key_code = keycode[0]
    else:
        key_code = keycode

    logger.debug(f"Processing keycode: {key_code}")

    if "KEY_" in key_code:
        return key_code.split("_")[1].replace("KP", "")
    return None
