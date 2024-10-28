import sys
import os
import logging
from multiprocessing import Process, Queue
import time
from dotenv import load_dotenv
from src.db import get_all_pins, get_all_rfids, is_user_allowed_access
from src.utils import hash_secret, unlock_door
from src.logger import logger
from src.reader.input_handler import read_input

load_dotenv()

def check_input(input_value):
    # Check if it's a PIN
    all_pins = get_all_pins()
    for pin in all_pins:
        if hash_secret(input_value, pin.salt) == pin.hashed_pin:
            if pin.user.role == "guest":
                if is_user_allowed_access(pin.user.id):
                    logger.info("Valid PIN used by guest with valid access schedule")
                    return True
                else:
                    logger.warning("Valid PIN used by guest outside of allowed schedule")
                    return False
            logger.info("Valid PIN used")
            return True

    # Check if it's an RFID
    all_rfids = get_all_rfids()
    for rfid in all_rfids:
        if hash_secret(input_value, rfid.salt) == rfid.hashed_uuid:
            if rfid.user.role == "guest":
                if is_user_allowed_access(rfid.user.id):
                    logger.info("Valid RFID used by guest with valid access schedule")
                    return True
                else:
                    logger.warning("Valid RFID used by guest outside of allowed schedule")
                    return False
            logger.info("Valid RFID used")
            return True

    logger.warning("Invalid PIN or RFID attempted")
    return False

def reader_process(input_queue, stdin=None):
    logger.info("Reader process started")
    INPUT_SOURCE = os.getenv("INPUT_SOURCE", "stdin")
    
    if INPUT_SOURCE == "evdev":
        try:
            from evdev import InputDevice, categorize, ecodes, list_devices
            # Use the existing input_test.py logic for evdev
            devices = [InputDevice(path) for path in list_devices()]
            device_dict = {dev.fd: dev for dev in devices}
            
            logger.info("Monitoring the following devices:")
            for device in devices:
                logger.info(f"{device.path}: {device.name}")
                
            while True:
                try:
                    from select import select
                    r, w, x = select(device_dict, [], [])
                    for fd in r:
                        device = device_dict[fd]
                        for event in device.read():
                            if event.type == ecodes.EV_KEY:
                                key_event = categorize(event)
                                if key_event.keystate == 1:  # Key down
                                    input_queue.put(str(key_event.keycode))
                except Exception as e:
                    logger.error(f"Error reading from device: {e}")
                    time.sleep(1)
        except ImportError:
            logger.error("evdev not available, falling back to stdin")
            INPUT_SOURCE = "stdin"
    
    if INPUT_SOURCE == "stdin":
        import sys
        import select
        
        # Use provided stdin if available
        stdin_fd = stdin if stdin is not None else sys.stdin.fileno()
        
        while True:
            try:
                # Check if there's data available to read
                rlist, _, _ = select.select([stdin_fd], [], [], 0.1)
                
                if rlist:
                    # Use os.read to read from the file descriptor
                    value = os.read(stdin_fd, 1024).decode().strip()
                    if not value:  # EOF
                        logger.info("EOF received, stopping reader process")
                        break
                        
                    if value:
                        input_queue.put(value)
                        if check_input(value):
                            unlock_door()
                            
            except KeyboardInterrupt:
                logger.info("Reader process stopped by keyboard interrupt")
                break
            except Exception as e:
                logger.error(f"Error in reader process: {e}")
                time.sleep(1)

class SubprocessReader:
    def __init__(self):
        self.process = None
        self.status = "stopped"
        self.input_queue = Queue()

    def start(self):
        if self.status == "stopped":
            # Create process with explicit stdin configuration
            self.process = Process(
                target=reader_process, 
                args=(self.input_queue,),
                # Ensure stdin is inherited properly
                kwargs={'stdin': sys.stdin.fileno()}
            )
            # Start process with stdin inheritance
            self.process._inherit_stdin = True
            self.process.start()
            self.status = "running"
            logger.info("Reader subprocess started")
        else:
            logger.warning("Reader is already running")

    def stop(self):
        if self.status == "running" and self.process:
            self.process.terminate()
            self.process.join()
            self.status = "stopped"
            logger.info("Reader subprocess stopped")
        else:
            logger.warning("Reader is not running")

    def get_status(self):
        return self.status
