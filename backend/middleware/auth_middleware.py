"""
Bezalel.AI — Authentication middleware / dependency.

Extracts the JWT from the ``bezalel_session`` HttpOnly cookie, validates
its signature and expiry, confirms that the corresponding session record
still exists in the database, and returns the authenticated ``User``.

Usage in routers::

    from middleware.auth_middleware import get_current_user

    @router.get("/protected")
    async def protected(user: User = Depends(get_current_user)):
        ...
"""

import hashlib
from datetime import datetime, timezone

from fastapi import Cookie, Depends, HTTPException, status
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database import get_db
from models.user import Session as SessionModel
from models.user import User


def _hash_token(token: str) -> str:
    """Return the SHA-256 hex digest of a JWT string."""
    return hashlib.sha256(token.encode()).hexdigest()


async def get_current_user(
    bezalel_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    FastAPI dependency that authenticates the request.

    Raises ``401 Unauthorized`` if the cookie is missing, the JWT is
    invalid or expired, or no matching session exists in the database.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # 1. Cookie must be present.
    if bezalel_session is None:
        raise credentials_exception

    # 2. Decode and validate the JWT.
    try:
        payload = jwt.decode(
            bezalel_session,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        user_id: str | None = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    # 3. Verify the session record exists and has not expired.
    token_hash = _hash_token(bezalel_session)
    result = await db.execute(
        select(SessionModel).where(SessionModel.token_hash == token_hash)
    )
    session_record = result.scalar_one_or_none()

    if session_record is None:
        raise credentials_exception

    if session_record.expires_at.replace(tzinfo=timezone.utc) < datetime.now(
        timezone.utc
    ):
        # Session expired — clean it up.
        await db.delete(session_record)
        await db.commit()
        raise credentials_exception

    # 4. Load and return the user.
    result = await db.execute(select(User).where(User.id == session_record.user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise credentials_exception

    return user
