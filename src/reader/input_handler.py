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
    for path in device_paths:
        device = InputDevice(path)
        try:
            if "keyboard" in device.name.lower() or "event" in device.path:
                keyboards.append(device)
            else:
                device.close()  # Close devices that are not keyboards
        except Exception as e:
            logger.error(f"Error accessing device {path}: {e}")
            device.close()
    return keyboards


def decode_keypad_input(input_sequence):
    return KEY_CODES.get(input_sequence, "")


async def capture_input():
    """Captures a single input sequence from configured input source (stdin or keyboard)"""
    if INPUT_SOURCE == "stdin":
        logger.info("Reading input from stdin")
        return await capture_console_input()
    else:
        logger.info("Reading input from evdev")
        try:
            # Create a queue for input events
            input_queue = asyncio.Queue()
            # Start the input reading task
            read_task = asyncio.create_task(handle_keyboard_devices(input_queue))

            try:
                # Just wait for the input without timeout
                result = await input_queue.get()
                read_task.cancel()  # Cancel the reading task once we have input
                return result
            except Exception as e:
                logger.error(f"Error in capture_input: {e}")
                try:
                    read_task.cancel()
                except Exception as cancel_exception:
                    logger.error(f"Error cancelling read_task: {cancel_exception}")
                return None
        except Exception as e:
            logger.error(f"Error in capture_input: {e}")
            return None


async def capture_console_input():
    """Captures input directly from console/terminal"""
    loop = asyncio.get_event_loop()
    try:
        # Remove wait_for and just use run_in_executor directly
        input_value = await loop.run_in_executor(
            None, input, "You can enter PIN or RFID now...\n"
        )
        return input_value.strip()
    except Exception as e:
        logger.error(f"Error in capture_console_input: {e}")
        return None


async def handle_keyboard_devices(input_queue):
    """Manages multiple keyboard devices and their input buffers"""
    try:
        keyboards = find_keyboards()
        if not keyboards:
            logger.error("No keyboards found.")
            return None

        # Create shared buffers
        input_buffer = deque(
            maxlen=MAX_INPUT_LENGTH
        )  # input buffer holds the individual characters of a PIN or RFID ID
        t9em_input_buffer = deque(
            maxlen=10
        )  # t9em input buffer holds the encoded input sequence of that specific keypad - after each ENTER, the buffer is decoded into a single character, which is then added to the input buffer. When an RFID is scanned, the buffer is directly filled with the actual value of the ID, meaning decoding will fail and the ID will be added to the input queue directly.

        # Create tasks for each keyboard
        keyboard_tasks = []
        for keyboard in keyboards:
            task = asyncio.create_task(
                handle_device_events(
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
                logger.error(
                    f"Error in handle_keyboard_devices during task cancellation: {e}"
                )
                raise
    except Exception as e:
        logger.error(f"Error in handle_keyboard_devices: {e}")
        raise


async def handle_device_events(device, input_buffer, t9em_input_buffer, input_queue):
    """Processes raw events from a single keyboard device"""
    timeout = int(os.getenv("INPUT_TIMEOUT", 10))
    timer_state = {"last_keypress": None}

    try:
        async for event in device.async_read_loop():
            if event.type != ecodes.EV_KEY or categorize(event).keystate != 1:
                continue

            current_time = asyncio.get_event_loop().time()
            key = parse_key_event(categorize(event).keycode)
            if not key:
                continue

            # Handle first keypress or timeout
            if not timer_state["last_keypress"] or (
                current_time - timer_state["last_keypress"] > timeout
            ):
                logger.debug("Timeout reached or first keypress, clearing buffers")
                await clear_input_buffers(input_buffer, t9em_input_buffer)
            timer_state["last_keypress"] = current_time

            # Handle input based on mode
            if INPUT_SOURCE == "t9em":
                if key == "ENTER":
                    await handle_t9em_sequence(
                        input_buffer, t9em_input_buffer, input_queue
                    )
                    timer_state["last_keypress"] = (
                        None  # Reset timer after complete input
                    )
                else:
                    t9em_input_buffer.append(key)
            else:
                if key == "ENTER":
                    await input_queue.put("".join(input_buffer))
                    await clear_input_buffers(input_buffer, t9em_input_buffer)
                    timer_state["last_keypress"] = (
                        None  # Reset timer after complete input
                    )
                elif key.isdigit() or key.isalpha():
                    input_buffer.append(key)

    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.error(f"Error reading keyboard events: {e}")
        raise
    finally:
        device.close()


def clear_input_buffers(input_buffer, t9em_input_buffer):
    """Clears all input buffers"""
    input_buffer.clear()
    t9em_input_buffer.clear()


async def handle_t9em_sequence(input_buffer, t9em_input_buffer, input_queue):
    """Processes T9 keypad input sequences"""
    input_sequence = "".join(t9em_input_buffer)
    decoded_key = decode_keypad_input(input_sequence)
    t9em_input_buffer.clear()  # Clear t9em buffer after processing

    if not decoded_key:  # RFID scan
        await input_queue.put(input_sequence)
        clear_input_buffers(
            input_buffer, t9em_input_buffer
        )  # to be sure - input buffer should be empty anyway
        return

    if decoded_key in ["*", "#"]:
        clear_input_buffers(input_buffer, t9em_input_buffer)
        return

    input_buffer.append(decoded_key)
    if len(input_buffer) >= int(PIN_LENGTH):
        await input_queue.put("".join(input_buffer))
        clear_input_buffers(input_buffer, t9em_input_buffer)


def parse_key_event(keycode):
    """Parses raw keycode into usable key value"""
    if isinstance(keycode, list):
        key_code = keycode[0]
    else:
        key_code = keycode

    logger.debug(f"Processing keycode: {key_code}")

    if "KEY_" in key_code:
        return key_code.split("_")[1].replace("KP", "")
    return None
