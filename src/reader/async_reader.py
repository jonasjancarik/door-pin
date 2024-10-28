import asyncio
from src.logger import logger
from src.db import get_all_pins, get_all_rfids, is_user_allowed_access
from src.reader.input_handler import read_input
from src.utils import hash_secret, unlock_door
from src.door_manager import door_manager

class AsyncReader:
    def __init__(self):
        self.input_queue = asyncio.Queue()
        self.status = "stopped"
        self.task_running = False
        self.reader_task = None

    def check_input(self, input_value):
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

        # If not a PIN, check if it's an RFID
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

    async def input_reader(self):
        while self.task_running:
            try:
                input_value = await read_input()
                if input_value:
                    await self.input_queue.put(input_value)
            except Exception as e:
                logger.error(f"Error in input reader: {e}")
                await asyncio.sleep(1)

    async def input_processor(self):
        while self.task_running:
            try:
                input_value = await asyncio.wait_for(self.input_queue.get(), timeout=1)
                if input_value and self.check_input(input_value):
                    await door_manager.unlock(unlock_door, 5)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Error in input processor: {e}")

    def start(self):
        if not self.task_running:
            self.task_running = True
            self.status = "running"
            loop = asyncio.get_event_loop()
            reader_task_1 = loop.create_task(self.input_reader())
            reader_task_2 = loop.create_task(self.input_processor())
            self.reader_task = asyncio.gather(reader_task_1, reader_task_2)
            logger.info("Reader started")
        else:
            logger.warning("Reader is already running")

    def stop(self):
        if self.task_running:
            self.task_running = False
            self.status = "stopped"
            if self.reader_task:
                self.reader_task.cancel()
            logger.info("Reader stopped")
        else:
            logger.warning("Reader is not running")

    def get_status(self):
        return self.status