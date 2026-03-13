"""
Bezalel.AI — Google Gmail integration service.

Handles OAuth token management (encrypt / decrypt with Fernet),
fetches emails from the past 3 years using the Gmail REST API,
extracts sender/recipient contacts, and supports incremental sync.
"""

import json
import re
from datetime import datetime, timedelta, timezone
from email.utils import parseaddr

import httpx
from cryptography.fernet import Fernet

from config import settings
from models.contact import Contact, Meeting, MeetingType

# ── Constants ────────────────────────────────────────────────────────────
GMAIL_API_BASE = "https://gmail.googleapis.com/gmail/v1/users/me"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
SYNC_WINDOW_YEARS = 3


# ── Token helpers ────────────────────────────────────────────────────────


def _get_fernet() -> Fernet:
    """Return a Fernet instance using the app-wide encryption key."""
    return Fernet(settings.ENCRYPTION_KEY.encode())


def decrypt_tokens(encrypted: str) -> dict:
    """Decrypt a Fernet-encrypted JSON token blob."""
    fernet = _get_fernet()
    raw = fernet.decrypt(encrypted.encode()).decode()
    return json.loads(raw)


def encrypt_tokens(token_data: dict) -> str:
    """Encrypt a token dict to a Fernet-encrypted string."""
    fernet = _get_fernet()
    return fernet.encrypt(json.dumps(token_data).encode()).decode()


async def refresh_access_token(refresh_token: str) -> dict:
    """
    Exchange a refresh token for a new access token via Google's
    OAuth token endpoint.
    """
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
        )
        resp.raise_for_status()
        return resp.json()


async def get_valid_access_token(encrypted_tokens: str) -> tuple[str, str]:
    """
    Decrypt stored tokens and refresh the access token if needed.

    Returns:
        (access_token, updated_encrypted_tokens)
    """
    tokens = decrypt_tokens(encrypted_tokens)
    refresh_token = tokens.get("refresh_token", "")

    # Always refresh to ensure validity (short-lived access tokens).
    new_tokens = await refresh_access_token(refresh_token)
    tokens["access_token"] = new_tokens["access_token"]

    return tokens["access_token"], encrypt_tokens(tokens)


# ── Email fetching ───────────────────────────────────────────────────────


def _parse_email_address(header_value: str) -> tuple[str, str]:
    """Parse 'Display Name <email@example.com>' into (name, email)."""
    name, addr = parseaddr(header_value)
    return name.strip(), addr.strip().lower()


def _extract_header(headers: list[dict], name: str) -> str:
    """Extract a specific header value from a Gmail message headers list."""
    for h in headers:
        if h.get("name", "").lower() == name.lower():
            return h.get("value", "")
    return ""


async def fetch_emails(
    access_token: str,
    after_date: datetime | None = None,
    page_token: str | None = None,
    max_results: int = 100,
) -> dict:
    """
    Fetch a page of email message IDs from Gmail.

    Args:
        access_token: Valid OAuth2 access token.
        after_date:   Only fetch emails after this date.
        page_token:   Token for pagination.
        max_results:  Max messages per page.

    Returns:
        Gmail API list response with ``messages`` and ``nextPageToken``.
    """
    params: dict[str, str | int] = {"maxResults": max_results}

    # Build query for date filtering.
    if after_date:
        date_str = after_date.strftime("%Y/%m/%d")
        params["q"] = f"after:{date_str}"

    if page_token:
        params["pageToken"] = page_token

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{GMAIL_API_BASE}/messages",
            headers={"Authorization": f"Bearer {access_token}"},
            params=params,
            timeout=30.0,
        )
        resp.raise_for_status()
        return resp.json()


async def get_email_detail(access_token: str, message_id: str) -> dict:
    """Fetch full message metadata for a single email."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{GMAIL_API_BASE}/messages/{message_id}",
            headers={"Authorization": f"Bearer {access_token}"},
            params={"format": "metadata", "metadataHeaders": "From,To,Cc,Subject,Date"},
            timeout=30.0,
        )
        resp.raise_for_status()
        return resp.json()


def extract_contacts_from_email(message_detail: dict) -> list[dict]:
    """
    Extract contact information from a single email's headers.

    Returns a list of dicts with ``full_name`` and ``email`` keys.
    """
    contacts: list[dict] = []
    headers = message_detail.get("payload", {}).get("headers", [])

    for header_name in ("From", "To", "Cc"):
        raw = _extract_header(headers, header_name)
        if not raw:
            continue

        # Handle comma-separated addresses.
        for addr_part in raw.split(","):
            name, email = _parse_email_address(addr_part.strip())
            if email and "@" in email:
                contacts.append({"full_name": name or email.split("@")[0], "email": email})

    return contacts


async def full_sync(
    encrypted_tokens: str,
) -> tuple[list[dict], list[dict], str]:
    """
    Perform a full email sync for the past 3 years.

    Returns:
        (contacts, meetings, updated_encrypted_tokens)
    """
    access_token, updated_tokens = await get_valid_access_token(encrypted_tokens)
    after_date = datetime.now(timezone.utc) - timedelta(days=SYNC_WINDOW_YEARS * 365)

    all_contacts: list[dict] = []
    all_meetings: list[dict] = []
    page_token: str | None = None

    while True:
        result = await fetch_emails(access_token, after_date=after_date, page_token=page_token)
        messages = result.get("messages", [])

        for msg_stub in messages:
            detail = await get_email_detail(access_token, msg_stub["id"])
            contacts = extract_contacts_from_email(detail)
            all_contacts.extend(contacts)

            headers = detail.get("payload", {}).get("headers", [])
            subject = _extract_header(headers, "Subject")
            date_str = _extract_header(headers, "Date")

            all_meetings.append({
                "subject": subject,
                "date": date_str,
                "meeting_type": MeetingType.EMAIL.value,
                "source": "gmail",
                "contacts": contacts,
            })

        page_token = result.get("nextPageToken")
        if not page_token:
            break

    return all_contacts, all_meetings, updated_tokens


async def incremental_sync(
    encrypted_tokens: str,
    last_sync_date: datetime,
) -> tuple[list[dict], list[dict], str]:
    """
    Perform an incremental sync from the last sync date.

    Returns:
        (contacts, meetings, updated_encrypted_tokens)
    """
    access_token, updated_tokens = await get_valid_access_token(encrypted_tokens)

    all_contacts: list[dict] = []
    all_meetings: list[dict] = []
    page_token: str | None = None

    while True:
        result = await fetch_emails(access_token, after_date=last_sync_date, page_token=page_token)
        messages = result.get("messages", [])

        for msg_stub in messages:
            detail = await get_email_detail(access_token, msg_stub["id"])
            contacts = extract_contacts_from_email(detail)
            all_contacts.extend(contacts)

            headers = detail.get("payload", {}).get("headers", [])
            subject = _extract_header(headers, "Subject")
            date_str = _extract_header(headers, "Date")

            all_meetings.append({
                "subject": subject,
                "date": date_str,
                "meeting_type": MeetingType.EMAIL.value,
                "source": "gmail",
                "contacts": contacts,
            })

        page_token = result.get("nextPageToken")
        if not page_token:
            break

    return all_contacts, all_meetings, updated_tokens
