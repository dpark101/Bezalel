"""
Bezalel.AI — Microsoft Outlook email integration via Graph API.

Handles OAuth token management, fetches emails from the past 3 years,
extracts contacts from sender/recipient fields, and supports incremental
sync using the Microsoft Graph ``$filter`` parameter.
"""

import json
from datetime import datetime, timedelta, timezone
from email.utils import parseaddr

import httpx
from cryptography.fernet import Fernet

from config import settings
from models.contact import MeetingType

# ── Constants ────────────────────────────────────────────────────────────
GRAPH_API_BASE = "https://graph.microsoft.com/v1.0"
MS_TOKEN_URL = "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
SYNC_WINDOW_YEARS = 3


# ── Token helpers ────────────────────────────────────────────────────────


def _get_fernet() -> Fernet:
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
    Exchange a refresh token for a new access token via Microsoft's
    OAuth2 token endpoint.
    """
    token_url = MS_TOKEN_URL.format(tenant=settings.MICROSOFT_TENANT_ID)
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            token_url,
            data={
                "client_id": settings.MICROSOFT_CLIENT_ID,
                "client_secret": settings.MICROSOFT_CLIENT_SECRET,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
                "scope": "Mail.Read Calendars.Read offline_access",
            },
        )
        resp.raise_for_status()
        return resp.json()


async def get_valid_access_token(encrypted_tokens: str) -> tuple[str, str]:
    """
    Decrypt stored tokens, refresh the access token, and return the
    new access token along with the re-encrypted token blob.
    """
    tokens = decrypt_tokens(encrypted_tokens)
    refresh_token = tokens.get("refresh_token", "")

    new_tokens = await refresh_access_token(refresh_token)
    tokens["access_token"] = new_tokens["access_token"]
    if "refresh_token" in new_tokens:
        tokens["refresh_token"] = new_tokens["refresh_token"]

    return tokens["access_token"], encrypt_tokens(tokens)


# ── Email fetching ───────────────────────────────────────────────────────


def _extract_contacts_from_message(message: dict) -> list[dict]:
    """
    Extract contact dicts from a Graph API mail message.

    Looks at ``from``, ``toRecipients``, and ``ccRecipients``.
    """
    contacts: list[dict] = []

    # Sender
    sender = message.get("from", {}).get("emailAddress", {})
    if sender.get("address"):
        contacts.append({
            "full_name": sender.get("name", sender["address"].split("@")[0]),
            "email": sender["address"].lower(),
        })

    # To + CC recipients
    for field in ("toRecipients", "ccRecipients"):
        for recipient in message.get(field, []):
            addr = recipient.get("emailAddress", {})
            if addr.get("address"):
                contacts.append({
                    "full_name": addr.get("name", addr["address"].split("@")[0]),
                    "email": addr["address"].lower(),
                })

    return contacts


async def fetch_emails(
    access_token: str,
    after_date: datetime | None = None,
    skip: int = 0,
    top: int = 100,
) -> dict:
    """
    Fetch a page of messages from the user's mailbox via Graph API.

    Args:
        access_token: Valid OAuth2 access token.
        after_date:   Only fetch messages received after this date.
        skip:         Number of results to skip (pagination).
        top:          Number of results per page.

    Returns:
        Graph API response dict with ``value`` (messages) and
        ``@odata.nextLink`` if more pages exist.
    """
    params: dict[str, str | int] = {
        "$top": top,
        "$skip": skip,
        "$select": "id,subject,from,toRecipients,ccRecipients,receivedDateTime,bodyPreview",
        "$orderby": "receivedDateTime desc",
    }

    if after_date:
        iso = after_date.strftime("%Y-%m-%dT%H:%M:%SZ")
        params["$filter"] = f"receivedDateTime ge {iso}"

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{GRAPH_API_BASE}/me/messages",
            headers={"Authorization": f"Bearer {access_token}"},
            params=params,
            timeout=30.0,
        )
        resp.raise_for_status()
        return resp.json()


async def full_sync(
    encrypted_tokens: str,
) -> tuple[list[dict], list[dict], str]:
    """
    Full sync of emails for the past 3 years.

    Returns:
        (contacts, meetings, updated_encrypted_tokens)
    """
    access_token, updated_tokens = await get_valid_access_token(encrypted_tokens)
    after_date = datetime.now(timezone.utc) - timedelta(days=SYNC_WINDOW_YEARS * 365)

    all_contacts: list[dict] = []
    all_meetings: list[dict] = []
    skip = 0

    while True:
        result = await fetch_emails(access_token, after_date=after_date, skip=skip)
        messages = result.get("value", [])
        if not messages:
            break

        for msg in messages:
            contacts = _extract_contacts_from_message(msg)
            all_contacts.extend(contacts)

            all_meetings.append({
                "subject": msg.get("subject", ""),
                "date": msg.get("receivedDateTime", ""),
                "meeting_type": MeetingType.EMAIL.value,
                "source": "outlook",
                "contacts": contacts,
            })

        # Check for next page.
        if "@odata.nextLink" not in result:
            break
        skip += len(messages)

    return all_contacts, all_meetings, updated_tokens


async def incremental_sync(
    encrypted_tokens: str,
    last_sync_date: datetime,
) -> tuple[list[dict], list[dict], str]:
    """
    Incremental sync from the last sync date.

    Returns:
        (contacts, meetings, updated_encrypted_tokens)
    """
    access_token, updated_tokens = await get_valid_access_token(encrypted_tokens)

    all_contacts: list[dict] = []
    all_meetings: list[dict] = []
    skip = 0

    while True:
        result = await fetch_emails(access_token, after_date=last_sync_date, skip=skip)
        messages = result.get("value", [])
        if not messages:
            break

        for msg in messages:
            contacts = _extract_contacts_from_message(msg)
            all_contacts.extend(contacts)

            all_meetings.append({
                "subject": msg.get("subject", ""),
                "date": msg.get("receivedDateTime", ""),
                "meeting_type": MeetingType.EMAIL.value,
                "source": "outlook",
                "contacts": contacts,
            })

        if "@odata.nextLink" not in result:
            break
        skip += len(messages)

    return all_contacts, all_meetings, updated_tokens
