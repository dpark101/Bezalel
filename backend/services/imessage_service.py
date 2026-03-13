"""
Bezalel.AI — Server-side iMessage processing service.

Handles:
  - Decryption of AES-256-CBC encrypted payloads from the macOS companion
  - Parsing messages into contact and meeting records
  - Rotating API key validation (keys regenerate every 7 days)
"""

import base64
import hashlib
import hmac
import json
import time
import uuid
from datetime import datetime, timezone

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.padding import PKCS7

from config import settings
from database import async_session_factory
from models.contact import Contact, Meeting, MeetingType

# ── Constants ────────────────────────────────────────────────────────────
KEY_ROTATION_SECONDS = 7 * 24 * 60 * 60  # 7 days
AES_BLOCK_SIZE = 128  # bits


# ── API Key Validation ───────────────────────────────────────────────────


def _current_key_epoch() -> int:
    """
    Return the current rotation epoch (integer number of 7-day periods
    since Unix epoch).
    """
    return int(time.time()) // KEY_ROTATION_SECONDS


def _derive_api_key(epoch: int) -> str:
    """
    Derive a deterministic API key for a given rotation epoch using
    HMAC-SHA256 of the master key and epoch counter.
    """
    message = f"{epoch}".encode()
    mac = hmac.new(settings.IMESSAGE_MASTER_KEY.encode(), message, hashlib.sha256)
    return mac.hexdigest()


def validate_api_key(api_key: str) -> bool:
    """
    Check whether ``api_key`` matches the current or previous rotation
    epoch.  Accepting the previous epoch provides a grace window during
    key rotation.
    """
    current_epoch = _current_key_epoch()
    valid_keys = {
        _derive_api_key(current_epoch),
        _derive_api_key(current_epoch - 1),
    }
    return api_key in valid_keys


def get_current_api_key() -> str:
    """Return the currently valid API key (for provisioning)."""
    return _derive_api_key(_current_key_epoch())


# ── Payload Decryption ───────────────────────────────────────────────────


def _derive_aes_key() -> bytes:
    """
    Derive a 256-bit AES key from the master key using SHA-256.
    """
    return hashlib.sha256(settings.IMESSAGE_MASTER_KEY.encode()).digest()


def decrypt_payload(encrypted_b64: str, iv_b64: str) -> list[dict]:
    """
    Decrypt an AES-256-CBC encrypted payload.

    Args:
        encrypted_b64: Base64-encoded ciphertext.
        iv_b64:        Base64-encoded initialization vector.

    Returns:
        Parsed list of message dicts from the decrypted JSON.

    Raises:
        ValueError: If decryption or JSON parsing fails.
    """
    key = _derive_aes_key()
    iv = base64.b64decode(iv_b64)
    ciphertext = base64.b64decode(encrypted_b64)

    cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
    decryptor = cipher.decryptor()
    padded = decryptor.update(ciphertext) + decryptor.finalize()

    # Remove PKCS7 padding.
    unpadder = PKCS7(AES_BLOCK_SIZE).unpadder()
    plaintext = unpadder.update(padded) + unpadder.finalize()

    data = json.loads(plaintext.decode("utf-8"))

    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "messages" in data:
        return data["messages"]

    raise ValueError("Unexpected payload structure after decryption")


# ── Message Processing ──────────────────────────────────────────────────


async def parse_and_store_messages(messages: list[dict]) -> dict:
    """
    Parse decrypted iMessage data and store contacts / meetings.

    Each message dict is expected to have:
      - ``sender``: phone number or email
      - ``sender_name``: display name (optional)
      - ``text``: message body
      - ``date``: ISO datetime string
      - ``chat_id``: conversation identifier (optional)

    Returns:
        Dict with ``contacts_created`` and ``meetings_created`` counts.
    """
    from sqlalchemy import select

    contacts_created = 0
    meetings_created = 0

    async with async_session_factory() as db:
        for msg in messages:
            sender = msg.get("sender", "").strip()
            sender_name = msg.get("sender_name", "").strip()
            text = msg.get("text", "").strip()
            date_str = msg.get("date")

            if not sender:
                continue

            # Determine if sender is email or phone.
            is_email = "@" in sender

            # Look for existing contact by email or phone.
            contact: Contact | None = None

            if is_email:
                result = await db.execute(
                    select(Contact).where(Contact.email_addresses.any(sender.lower()))
                )
                contact = result.scalar_one_or_none()
            else:
                result = await db.execute(
                    select(Contact).where(Contact.phone_numbers.any(sender))
                )
                contact = result.scalar_one_or_none()

            if contact is None:
                # Create new contact.
                contact = Contact(
                    full_name=sender_name or sender,
                    email_addresses=[sender.lower()] if is_email else None,
                    phone_numbers=[sender] if not is_email else None,
                    source_tags=["imessage"],
                )
                db.add(contact)
                await db.flush()
                contacts_created += 1

            # Ensure imessage source tag.
            if contact.source_tags is None:
                contact.source_tags = ["imessage"]
            elif "imessage" not in contact.source_tags:
                contact.source_tags = contact.source_tags + ["imessage"]

            # Create meeting record for the conversation.
            meeting_date = None
            if date_str:
                try:
                    meeting_date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                except ValueError:
                    pass

            meeting = Meeting(
                contact_id=contact.id,
                meeting_date=meeting_date,
                meeting_type=MeetingType.IMESSAGE,
                subject=f"iMessage with {contact.full_name}",
                summary=text[:500] if text else None,
                raw_content=text,
                source="imessage",
            )
            db.add(meeting)
            meetings_created += 1

        await db.commit()

    return {
        "contacts_created": contacts_created,
        "meetings_created": meetings_created,
    }
