import asyncio
from typing import Optional


class DoorManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DoorManager, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        self._unlock_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()

    async def unlock(self, unlock_function, duration: int):
        async with self._lock:
            # Cancel any existing unlock operation
            if self._unlock_task and not self._unlock_task.done():
                self._unlock_task.cancel()
                try:
                    await self._unlock_task
                except asyncio.CancelledError:
                    pass

            # Start new unlock operation
            self._unlock_task = asyncio.create_task(unlock_function(duration))

            # Return immediately while the task runs in the background
            return {"message": "Door unlock initiated"}


door_manager = DoorManager()
