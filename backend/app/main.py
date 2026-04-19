from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import sys
import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env file from backend root (one level up from app/)
_env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=_env_path)

# Fix python parsing path
sys.path.append(str(Path(__file__).parent))

from routers import upload
from routers import patient, chat, auth, history, doctor
from database import init_db

app = FastAPI(title="EpiChat Inference API", version="2.0")

# Build CORS origins list from env variable (for production) + local dev defaults
_default_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://localhost:8000",
]
_extra_origins = os.getenv("ALLOWED_ORIGINS", "")
_allowed_origins = _default_origins + [
    o.strip() for o in _extra_origins.split(",") if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include core routers
app.include_router(upload.router)
app.include_router(patient.router)
app.include_router(chat.router)
app.include_router(auth.router)
app.include_router(history.router)
app.include_router(doctor.router)


@app.on_event("startup")
def _startup():
    init_db()

@app.get("/")
def health_check():
    return {"status": "EpiChat Backend Online", "version": "2.0"}
