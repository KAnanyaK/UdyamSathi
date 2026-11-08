"""Vercel FastAPI entrypoint; static Vite files are served by the app."""
from backend.main import app

__all__ = ["app"]
