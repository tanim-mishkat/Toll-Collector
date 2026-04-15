"""Launch the backend API.

Usage:  python run_server.py
Then open:  http://127.0.0.1:8000/docs
"""
import uvicorn
from config import BACKEND_HOST, BACKEND_PORT

if __name__ == "__main__":
    uvicorn.run(
        "backend.app:app",
        host=BACKEND_HOST,
        port=BACKEND_PORT,
        reload=True,
    )
