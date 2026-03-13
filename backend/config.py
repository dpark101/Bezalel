"""
Bezalel.AI — Application configuration.

Loads all environment variables from a .env file using pydantic-settings.
Provides typed, validated settings for database, auth, email, OAuth,
encryption, and third-party integrations.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration pulled from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ── Database ──────────────────────────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://bezalel:bezalel@localhost:5432/bezalel"

    # ── Authentication / JWT ──────────────────────────────────────────────
    SECRET_KEY: str = "CHANGE-ME-IN-PRODUCTION"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRY_HOURS: int = 24
    # Account-lockout thresholds
    MAX_FAILED_LOGINS: int = 5
    LOCKOUT_MINUTES: int = 30

    # ── SMTP (for OTP emails) ────────────────────────────────────────────
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = "noreply@bezalel.ai"
    SMTP_USE_TLS: bool = True

    # ── Google OAuth ─────────────────────────────────────────────────────
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/api/auth/google/callback"

    # ── Microsoft OAuth ──────────────────────────────────────────────────
    MICROSOFT_CLIENT_ID: str = ""
    MICROSOFT_CLIENT_SECRET: str = ""
    MICROSOFT_REDIRECT_URI: str = "http://localhost:8000/api/auth/microsoft/callback"
    MICROSOFT_TENANT_ID: str = "common"

    # ── Anthropic (Claude AI) ────────────────────────────────────────────
    ANTHROPIC_API_KEY: str = ""

    # ── iMessage bridge ──────────────────────────────────────────────────
    IMESSAGE_MASTER_KEY: str = ""

    # ── Symmetric encryption (Fernet-compatible, 32-byte URL-safe b64) ──
    ENCRYPTION_KEY: str = ""

    # ── Frontend origin for CORS ─────────────────────────────────────────
    FRONTEND_ORIGIN: str = "http://localhost:3000"


# Singleton instance used throughout the application.
settings = Settings()
