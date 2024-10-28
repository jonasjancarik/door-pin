import os
import time
from dotenv import load_dotenv
from src.logger import logger
from src.reader.subprocess_reader import SubprocessReader

load_dotenv()

READER_MODE = os.getenv("READER_MODE", "async")

if READER_MODE == "async":
    from src.reader.async_reader import AsyncReader as Reader
else:
    from src.reader.subprocess_reader import SubprocessReader as Reader

reader = Reader()

def start_reader():
    reader.start()

def stop_reader():
    reader.stop()

def get_reader_status():
    return reader.get_status()

async def read_single_input(timeout):
    """For one-off input reading (like RFID registration)"""
    if READER_MODE == "async":
        # Use existing async implementation
        try:
            from src.reader.input_handler import read_input
            import asyncio
            
            read_task = asyncio.create_task(read_input())
            try:
                input_value = await asyncio.wait_for(read_task, timeout=timeout)
                return input_value
            except asyncio.TimeoutError:
                return None
            finally:
                if not read_task.done():
                    read_task.cancel()
                    try:
                        await read_task
                    except asyncio.CancelledError:
                        pass
        except Exception as e:
            logger.error(f"Error in read_single_input: {e}")
            return None
    else:
        # Subprocess implementation
        try:
            start_time = time.time()
            while time.time() - start_time < timeout:
                if not reader.input_queue.empty():
                    return reader.input_queue.get_nowait()
                time.sleep(0.1)  # Small sleep to prevent busy waiting
            return None
        except Exception as e:
            logger.error(f"Error in read_single_input: {e}")
            return None
