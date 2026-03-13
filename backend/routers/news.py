"""
Bezalel.AI — iMessage sync router.

Provides an endpoint for the macOS companion app to push encrypted
iMessage data into the Rolodex.

Note: despite the module name (``news.py`` as specified), this router
handles iMessage sync at ``/api/imessage/sync``.
"""

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel

from services.imessage_service import (
    decrypt_payload,
    parse_and_store_messages,
    validate_api_key,
)

router = APIRouter(prefix="/api/imessage", tags=["imessage"])


class IMessageSyncRequest(BaseModel):
    """
    Encrypted iMessage payload sent from the macOS companion app.

    Fields:
        api_key:   Rotating API key (regenerated every 7 days).
        payload:   AES-256 encrypted message data (base64-encoded).
        iv:        Initialization vector for AES-256-CBC (base64-encoded).
    """

    api_key: str
    payload: str
    iv: str


@router.post("/sync")
async def imessage_sync(body: IMessageSyncRequest, request: Request) -> dict:
    """
    Validate the rotating API key, decrypt the AES-256 payload, parse
    the messages, and merge them into contacts and meeting records.
    """
    # 1. Validate the rotating API key.
    if not validate_api_key(body.api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired API key",
        )

    # 2. Decrypt the payload.
    try:
        messages = decrypt_payload(body.payload, body.iv)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to decrypt payload",
        )

    # 3. Parse messages and store as contacts / meetings.
    result = await parse_and_store_messages(messages)

    return {
        "message": "iMessage sync completed",
        "contacts_created": result.get("contacts_created", 0),
        "meetings_created": result.get("meetings_created", 0),
    }
