"""Central config for the toll prototype."""
import os
import secrets
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()  # reads .env if present; env vars already set take precedence

# Video source:
#   - IP Webcam (Android):  "http://<phone-ip>:8080/video"
#   - Iriun / DroidCam:     usually integer index 1 or 2
#   - Laptop webcam:        0
#   - Local video file:     "sample.mp4"
VIDEO_SOURCE = os.environ.get("VIDEO_SOURCE", "http://192.168.0.103:8080/video")

# Process every Nth frame to keep CPU usage sane
FRAME_SKIP = 3

# Minimum OCR confidence to accept a plate read
MIN_OCR_CONFIDENCE = 0.4

# Seconds to suppress duplicate reads of the same plate
DEDUPE_WINDOW_SEC = 30

# Paths
PROJECT_ROOT = Path(__file__).parent
MODELS_DIR = PROJECT_ROOT / "models"
PLATE_MODEL_PATH = MODELS_DIR / "license_plate_detector.pt"

# Model download sources (tried in order). Any public YOLOv8 plate model works.
PLATE_MODEL_URLS = [
    # GitHub raw — Muhammad-Zeerak-Khan's ANPR repo
    "https://github.com/Muhammad-Zeerak-Khan/"
    "Automatic-License-Plate-Recognition-using-YOLOv8/"
    "raw/main/license_plate_detector.pt",
    # HuggingFace mirror (YOLOv11, also Ultralytics-compatible)
    "https://huggingface.co/morsetechlab/"
    "yolov11-license-plate-detection/resolve/main/"
    "yolov11n-license-plate-end2end.pt",
]

# Window display size (helps on small laptop screens)
DISPLAY_WIDTH = 960

# ---------- Phase 3: backend ----------
DB_PATH = PROJECT_ROOT / "toll.db"
# Forward-slash form avoids Windows backslash ambiguity in SQLAlchemy URLs.
# In production set DATABASE_URL env var to a PostgreSQL connection string.
DB_URL = os.environ.get(
    "DATABASE_URL",
    f"sqlite:///{DB_PATH.as_posix()}"
)
# Render/Neon expose postgres:// but SQLAlchemy 2 needs postgresql://
if DB_URL.startswith("postgres://"):
    DB_URL = DB_URL.replace("postgres://", "postgresql://", 1)

BACKEND_HOST = "127.0.0.1"
BACKEND_PORT = 8000
BACKEND_URL = os.environ.get(
    "BACKEND_URL",
    f"http://{BACKEND_HOST}:{BACKEND_PORT}"
)

# ---------- Security ----------
ENV = os.environ.get("ENV", "development")  # set to "production" on server

# Secret key used by the camera nodes to authenticate with the backend.
# In dev a random key is generated each run (fine — camera is local too).
# In production: set API_KEY env var to a stable secret on both server and camera.
API_KEY = os.environ.get("API_KEY", secrets.token_hex(32))

# Comma-separated list of allowed CORS origins for the dashboard.
# Example: "https://your-dashboard.streamlit.app,https://your-api.onrender.com"
_raw_origins = os.environ.get("ALLOWED_ORIGINS", "http://localhost:8501")
ALLOWED_ORIGINS: list[str] = [o.strip() for o in _raw_origins.split(",") if o.strip()]

# Identity this camera node reports as
GANTRY_ID = "PADMA_BRIDGE_NB"

# Flat toll rates in BDT by vehicle class at this gantry.
# (Real system: matrix of gantry x class x time-of-day.)
TOLL_RATES_BDT = {
    "motorcycle": 50,
    "car": 150,
    "cng": 50,
    "pickup": 250,
    "bus": 500,
    "truck": 750,
    "unknown": 150,
}

# Default class when vehicle is unregistered / not classified yet
DEFAULT_VEHICLE_CLASS = "car"

# ---------- Phase 4: notifications ----------
# Optional Telegram bot for real phone buzz during demos.
# Get a token from @BotFather, then:
#   $env:TELEGRAM_BOT_TOKEN="123456:ABC..."
#   $env:TELEGRAM_CHAT_ID="987654321"
# Leave empty to stay in SMS-mock-only mode.
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

# Branding shown in every outbound message
SMS_SENDER_NAME = "ShohojToll"
TOLL_HELPLINE = "16123"
PAY_DEADLINE_DAYS = 7

# ---------- Phase 6: enforcement ----------
# Background job escalates UNPAID events through REMINDED -> LATE -> FINED -> BLOCKED.
# Times are in SECONDS so the whole lifecycle can be demo'd in ~15 minutes.
# For production, replace with days: REMINDED=7d, LATE=15d, FINED=30d, BLOCKED=180d.
ENFORCEMENT_ENABLED = True
ENFORCEMENT_TICK_SEC = 20  # how often the background loop wakes up
ENFORCEMENT_TIMINGS_SEC = {
    "REMINDED": 120,   # 2 min  — 2nd SMS, no money change
    "LATE":     300,   # 5 min  — add late fee (doubles total)
    "FINED":    600,   # 10 min — add fine (total = 10x base)
    "BLOCKED":  900,   # 15 min — flag vehicle.brta_blocked = True
}

# Money added at each escalation (multiplier × base toll).
LATE_FEE_MULTIPLIER = 1.0   # late_fee = 1× base    (total now 2×)
FINE_MULTIPLIER     = 8.0   # fine     = 8× base    (total now 10×)
