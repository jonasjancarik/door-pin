import asyncio
import logging
import utils
import argparse
from dotenv import load_dotenv
import os
import db
from collections import deque

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
    parser.add_argument(
        "--input-mode",
        choices=["standard", "special"],
        default=os.getenv("INPUT_MODE", "standard"),
        help="Input mode: 'standard' for regular input, 'special' for T9 key code input",
    )
    return parser.parse_args()


args = parse_args()
RFID_LENGTH = args.rfid_length or int(os.getenv("RFID_LENGTH", 10))
INPUT_MODE = args.input_mode

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


async def handle_keyboard(keyboard):
    pin_buffer = deque(maxlen=args.pin_length)
    last_input_time = asyncio.get_event_loop().time()
    logging.info(f"Using keyboard: {keyboard.name} at {keyboard.path}")
    print("Enter PIN or scan RFID: ", end="", flush=True)

    try:
        async for event in keyboard.async_read_loop():
            current_time = asyncio.get_event_loop().time()
            if current_time - last_input_time > args.timeout:
                pin_buffer.clear()
                logging.info("Input reset due to timeout.")
                print("\nEnter PIN or scan RFID: ", end="", flush=True)

            last_input_time = current_time

            if event.type == ecodes.EV_KEY:
                data = categorize(event)
                if data.keystate == 1:  # Key down events only
                    key = process_key(data.keycode)

                    if INPUT_MODE == "special":
                        handle_special_input(key, pin_buffer)
                    else:
                        handle_standard_input(key, pin_buffer)

            logging.debug(f"Current input: {''.join(pin_buffer)}")

    except Exception as e:
        logging.error(f"Error handling keyboard {keyboard.path}: {e}")


def process_key(keycode):
    if isinstance(keycode, list):
        key_code = keycode[0]
    else:
        key_code = keycode

    if "KEY_" in key_code:
        return key_code.split("_")[1].replace("KP", "")
    return None


def handle_special_input(key, pin_buffer):
    if key:
        digit = KEY_CODES.get(key.zfill(4))
        if digit:
            pin_buffer.append(digit)
            input_pin = "".join(pin_buffer)
            if len(pin_buffer) == args.pin_length and check_input(input_pin):
                open_door()
                pin_buffer.clear()


def handle_standard_input(key, pin_buffer):
    if key and (key.isdigit() or key.isalpha()):
        pin_buffer.append(key)
        input_pin = "".join(pin_buffer)
        if len(input_pin) >= args.pin_length and check_input(input_pin):
            open_door()
            pin_buffer.clear()


async def main():
    keyboards = find_keyboards()
    if not keyboards:
        logging.error("No keyboards found.")
        return

    tasks = [asyncio.create_task(handle_keyboard(keyboard)) for keyboard in keyboards]
    await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())
