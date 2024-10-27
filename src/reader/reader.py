import os
import src.utils as utils
from dotenv import load_dotenv
from src.db import get_all_pins, get_all_rfids, is_user_allowed_access
from src.reader.input_handler import read_input
from src.logger import logger
from src.door_manager import door_manager
import asyncio

load_dotenv()
INPUT_TIMEOUT = int(os.getenv("INPUT_TIMEOUT", 10))

input_queue = asyncio.Queue()
reader_status = "stopped"
task_running = False
reader_task = None


def check_input(input_value):
    # Check if it's a PIN
    all_pins = get_all_pins()
    for pin in all_pins:
        if utils.hash_secret(input_value, pin.salt) == pin.hashed_pin:
            # If it's a guest user, check their access schedule
            if pin.user.role == "guest":
                if is_user_allowed_access(pin.user.id):
                    logger.info("Valid PIN used by guest with valid access schedule")
                    return True
                else:
                    logger.warning(
                        "Valid PIN used by guest outside of allowed schedule"
                    )
                    return False
            # For non-guest users, allow access
            logger.info("Valid PIN used")
            return True

    # If not a PIN, check if it's an RFID
    all_rfids = get_all_rfids()
    for rfid in all_rfids:
        if utils.hash_secret(input_value, rfid.salt) == rfid.hashed_uuid:
            # If it's a guest user, check their access schedule
            if rfid.user.role == "guest":
                if is_user_allowed_access(rfid.user.id):
                    logger.info("Valid RFID used by guest with valid access schedule")
                    return True
                else:
                    logger.warning(
                        "Valid RFID used by guest outside of allowed schedule"
                    )
                    return False
            # For non-guest users, allow access
            logger.info("Valid RFID used")
            return True

    logger.warning("Invalid PIN or RFID attempted (this is normal after /rfids/read)")
    return False


async def input_reader():
    """Continuously reads input and puts it into the queue"""
    while task_running:
        try:
            input_value = await read_input()
            if input_value:
                await input_queue.put(input_value)
            else:
                # If we get None (timeout), just continue the loop to start reading again
                # todo: probably not needed
                logger.debug("Input timeout reached, starting new read cycle")
                continue
        except asyncio.InvalidStateError:
            logger.warning("Invalid state in input reader, resetting...")
            await asyncio.sleep(1)
        except asyncio.CancelledError:
            logger.info("Input reader cancelled")
            break
        except Exception as e:
            logger.error(f"Error in input reader: {e}")
            await asyncio.sleep(1)


async def input_processor():
    """Processes input from the queue"""
    while task_running:
        try:
            # Use a timeout here to allow checking task_running periodically
            input_value = await asyncio.wait_for(input_queue.get(), timeout=1)
            logger.debug(f"Input value: {input_value}")
            if input_value:
                if check_input(input_value) is True:
                    await door_manager.unlock(
                        utils.unlock_door, utils.RELAY_ACTIVATION_TIME
                    )
                else:
                    logger.debug(f"Invalid input: {input_value}")
        except asyncio.TimeoutError:
            logger.debug("Timeout reached in input processor")
            continue  # Just continue if no input received
        except asyncio.CancelledError:
            logger.info("Input processor cancelled")
            break
        except Exception as e:
            logger.error(f"Error in input processor: {e}")


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
        logger.info("Reader started")
    else:
        logger.warning("Reader is already running")


async def stop_reader():
    global task_running, reader_status, reader_task
    if task_running:
        task_running = False
        reader_status = "stopped"
        if reader_task:
            reader_task.cancel()
            try:
                await reader_task
            except asyncio.CancelledError:
                pass  # Expected when cancelling tasks
            except Exception as e:
                logger.error(f"Error during reader shutdown: {e}")
            finally:
                logger.info("Reader stop requested")
    else:
        logger.warning("Reader is not running")


def get_reader_status():
    """Returns the current status of the reader ('running' or 'stopped')"""
    return reader_status


async def read_single_input(timeout):
    """For one-off input reading (like RFID registration)"""
    try:
        # Start a temporary reading task
        read_task = asyncio.create_task(read_input())

        try:
            # Wait for input with timeout
            input_value = await asyncio.wait_for(read_task, timeout=timeout)
            return input_value
        except asyncio.TimeoutError:
            return None
        finally:
            # Always clean up the task
            if not read_task.done():
                read_task.cancel()
                try:
                    await read_task
                except asyncio.CancelledError:
                    pass
    except Exception as e:
        logger.error(f"Error in read_single_input: {e}")
        return None
