import uvicorn
import os
import logging
from logging.handlers import RotatingFileHandler
from fastapi import FastAPI, APIRouter, Depends
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from contextlib import asynccontextmanager
from src.reader.reader import start_reader, stop_reader
from src.api.routes.auth import router as auth_router
from src.api.routes.users import router as users_router
from src.api.routes.rfids import router as rfids_router
from src.api.routes.pins import router as pins_router
from src.api.routes.apartments import router as apartments_router
from src.api.routes.guests import router as guests_router
from src.api.routes.doors import router as doors_router
from src.api.routes.reader import router as reader_router
from src.api.routes.api_keys import router as api_keys_router
from src.api.routes.health import router as health_router
from src.api.routes.logs import router as logs_router
from src.api.exceptions import configure_exception_handlers
from src.api.dependencies import get_current_user

load_dotenv()

# Create logs directory if it doesn't exist
LOGS_DIR = "logs"
if not os.path.exists(LOGS_DIR):
    os.makedirs(LOGS_DIR)

# Configure logging
log_formatter = logging.Formatter(
    "%(asctime)s - %(levelname)s - %(pathname)s:%(lineno)d - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log_file = os.path.join(LOGS_DIR, "app.log")

# File Handler
file_handler = RotatingFileHandler(log_file, maxBytes=1024 * 1024 * 5, backupCount=5)
file_handler.setFormatter(log_formatter)
file_handler.setLevel(logging.INFO)

# Console Handler
console_handler = logging.StreamHandler()
console_handler.setFormatter(log_formatter)
console_handler.setLevel(logging.INFO)

# Get root logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.addHandler(file_handler)
logger.addHandler(console_handler)

# Get a specific logger for the app if needed, or use the root logger
app_logger = logging.getLogger("api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    app_logger.info("Application startup: Starting RFID reader...")
    start_reader()
    yield
    app_logger.info("Application shutdown: Stopping RFID reader...")
    await stop_reader()


app = FastAPI(lifespan=lifespan)

origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create a new router for authenticated routes
authenticated_router = APIRouter(dependencies=[Depends(get_current_user)])

# Include all routers that require authentication
authenticated_router.include_router(users_router)
authenticated_router.include_router(rfids_router)
authenticated_router.include_router(pins_router)
authenticated_router.include_router(apartments_router)
authenticated_router.include_router(guests_router)
authenticated_router.include_router(doors_router)
authenticated_router.include_router(reader_router)
authenticated_router.include_router(api_keys_router)
authenticated_router.include_router(health_router)
authenticated_router.include_router(logs_router)

# Add the authenticated router to the app
app.include_router(authenticated_router)

# Include the auth router separately (it contains the /magic-links and /tokens endpoints)
app.include_router(auth_router)

# Configure exception handlers
configure_exception_handlers(app)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app_logger.info(
        f"Starting server on {os.environ.get('API_HOST', 'localhost')}:{port}"
    )
    uvicorn.run(app, host=os.environ.get("API_HOST", "localhost"), port=port)
