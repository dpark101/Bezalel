"""
Bezalel.AI — Authentication router.

Endpoints:
  POST /api/auth/login         — validate credentials, send OTP email
  POST /api/auth/verify-otp    — verify OTP, issue JWT session cookie
  POST /api/auth/logout        — revoke session, clear cookie
  GET  /api/auth/me            — return current user info
  GET  /api/auth/google        — redirect to Google OAuth consent
  GET  /api/auth/google/callback
  GET  /api/auth/microsoft     — redirect to Microsoft OAuth consent
  GET  /api/auth/microsoft/callback
"""

import hashlib
import uuid
from datetime import datetime, timedelta, timezone

import pyotp
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from jose import jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import RedirectResponse

from config import settings
from database import get_db
from middleware.auth_middleware import get_current_user
from models.user import Session as SessionModel
from models.user import User
from services.email_service import send_otp_email

router = APIRouter(prefix="/api/auth", tags=["auth"])

# ── Password hashing (bcrypt, cost factor 12) ───────────────────────────
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)

# ── In-memory OTP store (maps pre-auth token -> (user_id, otp, expiry))
# In production, replace with Redis or a DB-backed store.
_otp_store: dict[str, tuple[uuid.UUID, str, datetime]] = {}


# ── Request / response schemas ──────────────────────────────────────────

class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    pre_auth_token: str
    message: str = "OTP sent to your email address."


class OTPVerifyRequest(BaseModel):
    pre_auth_token: str
    otp_code: str


class UserResponse(BaseModel):
    id: str
    email: str
    created_at: str
    last_login: str | None


# ── Helpers ──────────────────────────────────────────────────────────────

def _hash_token(token: str) -> str:
    """SHA-256 hex digest of a raw JWT."""
    return hashlib.sha256(token.encode()).hexdigest()


def _create_jwt(user_id: uuid.UUID, expires_delta: timedelta) -> str:
    """Create a signed JWT with ``sub`` and ``exp`` claims."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + expires_delta,
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


# ── POST /login ─────────────────────────────────────────────────────────

@router.post("/login", response_model=LoginResponse)
async def login(
    body: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> LoginResponse:
    """
    Validate email + password.  On success, generate a 6-digit TOTP code,
    send it via email, and return a pre-auth token the client must present
    when verifying the OTP.
    """
    # Look up user.
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    # Check account lockout.
    if user.locked_until and user.locked_until.replace(tzinfo=timezone.utc) > datetime.now(timezone.utc):
        remaining = int((user.locked_until.replace(tzinfo=timezone.utc) - datetime.now(timezone.utc)).total_seconds() / 60)
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail=f"Account locked. Try again in {remaining + 1} minutes.",
        )

    # Verify password.
    if not pwd_context.verify(body.password, user.hashed_password):
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= settings.MAX_FAILED_LOGINS:
            user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=settings.LOCKOUT_MINUTES)
        await db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    # Reset failed attempts on successful password check.
    user.failed_login_attempts = 0
    user.locked_until = None
    await db.commit()

    # Generate 6-digit OTP using pyotp (time-based, 10-minute window).
    if not user.totp_secret:
        user.totp_secret = pyotp.random_base32()
        await db.commit()

    totp = pyotp.TOTP(user.totp_secret, interval=600, digits=6)
    otp_code = totp.now()

    # Store OTP context with a pre-auth token.
    pre_auth_token = str(uuid.uuid4())
    _otp_store[pre_auth_token] = (
        user.id,
        otp_code,
        datetime.now(timezone.utc) + timedelta(minutes=10),
    )

    # Send OTP email (fire-and-forget style; log errors but don't block).
    try:
        await send_otp_email(user.email, otp_code)
    except Exception:
        # In production, log this properly.
        pass

    return LoginResponse(pre_auth_token=pre_auth_token)


# ── POST /verify-otp ────────────────────────────────────────────────────

@router.post("/verify-otp")
async def verify_otp(
    body: OTPVerifyRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Verify the 6-digit OTP code.  On success, issue a JWT inside an
    HttpOnly secure cookie and create a session record in the database.
    """
    stored = _otp_store.pop(body.pre_auth_token, None)
    if stored is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired pre-auth token")

    user_id, expected_otp, expiry = stored

    # Check expiry.
    if datetime.now(timezone.utc) > expiry:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="OTP has expired")

    # Validate OTP code.
    if body.otp_code != expected_otp:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid OTP code")

    # Issue JWT.
    expires_delta = timedelta(hours=settings.JWT_EXPIRY_HOURS)
    token = _create_jwt(user_id, expires_delta)
    token_hash = _hash_token(token)

    # Persist session record.
    client_ip = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    if not client_ip and request.client:
        client_ip = request.client.host

    session_record = SessionModel(
        user_id=user_id,
        token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) + expires_delta,
        ip_address=client_ip or None,
    )
    db.add(session_record)

    # Update last_login timestamp.
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user:
        user.last_login = datetime.now(timezone.utc)
    await db.commit()

    # Set HttpOnly secure cookie.
    response.set_cookie(
        key="bezalel_session",
        value=token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=int(expires_delta.total_seconds()),
        path="/",
    )

    return {"message": "Authenticated successfully"}


# ── POST /logout ─────────────────────────────────────────────────────────

@router.post("/logout")
async def logout(
    response: Response,
    user: User = Depends(get_current_user),
    bezalel_session: str | None = __import__("fastapi").Cookie(default=None),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Clear the session cookie and delete the session record."""
    if bezalel_session:
        token_hash = _hash_token(bezalel_session)
        result = await db.execute(
            select(SessionModel).where(SessionModel.token_hash == token_hash)
        )
        session_record = result.scalar_one_or_none()
        if session_record:
            await db.delete(session_record)
            await db.commit()

    response.delete_cookie("bezalel_session", path="/")
    return {"message": "Logged out successfully"}


# ── GET /me ──────────────────────────────────────────────────────────────

@router.get("/me", response_model=UserResponse)
async def me(user: User = Depends(get_current_user)) -> UserResponse:
    """Return the authenticated user's profile."""
    return UserResponse(
        id=str(user.id),
        email=user.email,
        created_at=user.created_at.isoformat(),
        last_login=user.last_login.isoformat() if user.last_login else None,
    )


# ── Google OAuth ─────────────────────────────────────────────────────────

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_SCOPES = [
    "openid",
    "email",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/calendar.readonly",
]


@router.get("/google")
async def google_redirect() -> RedirectResponse:
    """Redirect the user to Google's OAuth consent screen."""
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(GOOGLE_SCOPES),
        "access_type": "offline",
        "prompt": "consent",
    }
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return RedirectResponse(url=f"{GOOGLE_AUTH_URL}?{query}")


@router.get("/google/callback")
async def google_callback(
    code: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Exchange the authorization code for tokens, encrypt them, and store
    on the user record.
    """
    import httpx
    from cryptography.fernet import Fernet

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "redirect_uri": settings.GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code",
            },
        )
        if resp.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to exchange Google auth code")
        tokens = resp.text

    # Encrypt tokens with Fernet before storing.
    fernet = Fernet(settings.ENCRYPTION_KEY.encode())
    user.google_tokens_encrypted = fernet.encrypt(tokens.encode()).decode()
    await db.commit()

    return {"message": "Google account connected successfully"}


# ── Microsoft OAuth ──────────────────────────────────────────────────────

MS_AUTH_URL = "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/authorize"
MS_TOKEN_URL = "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
MS_SCOPES = [
    "openid",
    "email",
    "Mail.Read",
    "Calendars.Read",
    "offline_access",
]


@router.get("/microsoft")
async def microsoft_redirect() -> RedirectResponse:
    """Redirect the user to Microsoft's OAuth consent screen."""
    auth_url = MS_AUTH_URL.format(tenant=settings.MICROSOFT_TENANT_ID)
    params = {
        "client_id": settings.MICROSOFT_CLIENT_ID,
        "redirect_uri": settings.MICROSOFT_REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(MS_SCOPES),
        "response_mode": "query",
    }
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return RedirectResponse(url=f"{auth_url}?{query}")


@router.get("/microsoft/callback")
async def microsoft_callback(
    code: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Exchange the authorization code for tokens, encrypt them, and store
    on the user record.
    """
    import httpx
    from cryptography.fernet import Fernet

    token_url = MS_TOKEN_URL.format(tenant=settings.MICROSOFT_TENANT_ID)

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            token_url,
            data={
                "code": code,
                "client_id": settings.MICROSOFT_CLIENT_ID,
                "client_secret": settings.MICROSOFT_CLIENT_SECRET,
                "redirect_uri": settings.MICROSOFT_REDIRECT_URI,
                "grant_type": "authorization_code",
            },
        )
        if resp.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to exchange Microsoft auth code")
        tokens = resp.text

    # Encrypt tokens with Fernet before storing.
    fernet = Fernet(settings.ENCRYPTION_KEY.encode())
    user.microsoft_tokens_encrypted = fernet.encrypt(tokens.encode()).decode()
    await db.commit()

    return {"message": "Microsoft account connected successfully"}
