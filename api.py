import uvicorn
import os
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
from src.api.exceptions import configure_exception_handlers
from src.api.dependencies import get_current_user

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    start_reader()
    yield
    stop_reader()


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
authenticated_router = APIRouter()

# Include all routers that require authentication
authenticated_router.include_router(users_router)
authenticated_router.include_router(rfids_router)
authenticated_router.include_router(pins_router)
authenticated_router.include_router(apartments_router)
authenticated_router.include_router(guests_router)
authenticated_router.include_router(doors_router)
authenticated_router.include_router(reader_router)
authenticated_router.include_router(api_keys_router)

# Add the authentication dependency to the authenticated router
app.include_router(authenticated_router, dependencies=[Depends(get_current_user)])

# Include the auth router separately (it contains the /magic-links and /tokens endpoints)
app.include_router(auth_router)

# Configure exception handlers
configure_exception_handlers(app)

if __name__ == "__main__":
    port = int(os.environ.get("API_PORT", 8000))
    uvicorn.run(app, host=os.environ.get("API_HOST", "localhost"), port=port)
