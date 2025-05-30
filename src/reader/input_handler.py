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
    device_paths = list_devices()
    keyboards = []
    logger.debug(f"Found {len(device_paths)} input devices")

    for path in device_paths:
        device = InputDevice(path)
        try:
            logger.debug(f"Checking device: {device.path} - {device.name}")
            # Be more specific about what we consider a keyboard
            device_name_lower = device.name.lower()
            if (
                "keyboard" in device_name_lower
                or "keypad" in device_name_lower
                or "rfid" in device_name_lower
                or (
                    "event" in device.path
                    and any(
                        cap in device.capabilities().get(1, [])
                        for cap in [2, 3, 4, 5, 6, 7, 8, 9, 10]
                    )
                )
            ):  # Check for digit keys
                keyboards.append(device)
                logger.info(f"Added keyboard device: {device.path} - {device.name}")
            else:
                device.close()  # Close devices that are not keyboards
        except Exception as e:
            logger.error(f"Error accessing device {path}: {e}")
            device.close()

    logger.info(f"Found {len(keyboards)} keyboard devices")
    return keyboards


def decode_keypad_input(input_sequence):
    return KEY_CODES.get(input_sequence, "")


async def read_input():
    if INPUT_SOURCE == "stdin":
        logger.info("Reading input from stdin")
        return await read_stdin()
    else:
        logger.info("Reading input from evdev")
        try:
            # Create a queue for input events
            input_queue = asyncio.Queue()
            # Start the input reading task
            read_task = asyncio.create_task(read_evdev(input_queue))

            try:
                # Just wait for the input without timeout
                result = await input_queue.get()
                read_task.cancel()  # Cancel the reading task once we have input
                return result
            except Exception as e:
                logger.error(f"Error in read_input: {e}")
                try:
                    read_task.cancel()
                except Exception as cancel_exception:
                    logger.error(f"Error cancelling read_task: {cancel_exception}")
                return None
        except Exception as e:
            logger.error(f"Error in read_input: {e}")
            return None


async def read_stdin():
    loop = asyncio.get_event_loop()
    try:
        # Remove wait_for and just use run_in_executor directly
        input_value = await loop.run_in_executor(
            None, input, "You can enter PIN or RFID now...\n"
        )
        return input_value.strip()
    except Exception as e:
        logger.error(f"Error in read_stdin: {e}")
        return None


async def read_evdev(input_queue):
    try:
        keyboards = find_keyboards()
        if not keyboards:
            logger.error("No keyboards found.")
            return None

        # Create shared buffers and result flag
        input_buffer = deque(maxlen=MAX_INPUT_LENGTH)
        t9em_input_buffer = deque(maxlen=10)
        result_found = asyncio.Event()  # Flag to prevent duplicate results

        # Create tasks for each keyboard
        keyboard_tasks = []
        for keyboard in keyboards:
            task = asyncio.create_task(
                read_keyboard_events(
                    keyboard, input_buffer, t9em_input_buffer, input_queue, result_found
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
                logger.error(f"Error in read_evdev during task cancellation: {e}")
                raise
    except Exception as e:
        logger.error(f"Error in read_evdev: {e}")
        raise


async def read_keyboard_events(
    device, input_buffer, t9em_input_buffer, input_queue, result_found
):
    timeout = int(os.getenv("INPUT_TIMEOUT", 10))
    try:
        first_key_received = False
        start_time = None

        async for event in device.async_read_loop():
            # Skip processing if result already found
            if result_found.is_set():
                break

            if event.type == ecodes.EV_KEY:
                data = categorize(event)
                if data.keystate == 1:  # Key down events only
                    # Start timing from first keypress
                    if not first_key_received:
                        first_key_received = True
                        start_time = asyncio.get_event_loop().time()

                    key = process_key(data.keycode)
                    if key:
                        if start_time is not None:
                            if asyncio.get_event_loop().time() - start_time > timeout:
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
                                    if (
                                        decoded_key == "*" or decoded_key == "#"
                                    ):  # these buttons reset the input buffer
                                        input_buffer.clear()
                                        t9em_input_buffer.clear()
                                        first_key_received = False
                                        start_time = None
                                    else:
                                        input_buffer.append(decoded_key)
                                else:  # this means an rfid was scanned
                                    if not result_found.is_set():
                                        result_found.set()
                                        await input_queue.put(input_sequence)
                                    input_buffer.clear()  # should be empty anyway
                                # check if the input buffer is the length of the PIN_LENGTH or longer
                                if len(input_buffer) >= PIN_LENGTH:
                                    if not result_found.is_set():
                                        result_found.set()
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
                                if not result_found.is_set():
                                    result_found.set()
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
    finally:
        device.close()  # Ensure the InputDevice is closed properly


def process_key(keycode):
    if isinstance(keycode, list):
        key_code = keycode[0]
    else:
        key_code = keycode

    logger.debug(f"Processing keycode: {key_code}")

    if "KEY_" in key_code:
        return key_code.split("_")[1].replace("KP", "")
    return None
