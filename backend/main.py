"""
Bezalel.AI — FastAPI application entry point.

Creates the FastAPI app, registers all routers, adds middleware,
configures CORS, and manages the database lifecycle.

Run with::

    uvicorn main:app --host 127.0.0.1 --port 8000
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from database import engine
from middleware.rate_limit_middleware import RateLimitMiddleware
from routers import auth, dashboard, news, rolodex

# ── Logging ──────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger("bezalel")


# ── Lifecycle ────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown hooks for the async DB engine."""
    logger.info("Bezalel.AI backend starting up")
    yield
    logger.info("Bezalel.AI backend shutting down")
    await engine.dispose()


# ── App ──────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Bezalel.AI",
    description="Personal AI-powered CRM — aggregates contacts from email, calendar, LinkedIn, and iMessage.",
    version="0.1.0",
    lifespan=lifespan,
)

# ── CORS ─────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Rate limiting ────────────────────────────────────────────────────────
app.add_middleware(RateLimitMiddleware)

# ── Routers ──────────────────────────────────────────────────────────────
app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(rolodex.router)
app.include_router(news.router)


# ── Health check ─────────────────────────────────────────────────────────
@app.get("/api/health", tags=["system"])
async def health_check() -> dict:
    """Simple liveness probe."""
    return {"status": "ok"}
