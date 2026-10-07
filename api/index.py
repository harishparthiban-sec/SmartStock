"""
Vercel Serverless Function entry point for SmartStock FastAPI backend.

This file wraps the FastAPI app with Mangum so it can run as an AWS Lambda /
Vercel serverless function. Vercel routes /api/* to this file via vercel.json.

All business logic lives in src/inventory/ and src/api/server.py — this file
is purely the ASGI adapter shim.
"""
import sys
import os

# Ensure the repo root is on the Python path so `src.*` imports resolve
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mangum import Mangum
from src.api.server import app

# Mangum wraps the FastAPI ASGI app for serverless execution
handler = Mangum(app, lifespan="off")
