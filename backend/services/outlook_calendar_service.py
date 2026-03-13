"""
Bezalel.AI — Outlook Calendar integration via Microsoft Graph API.

Fetches calendar events with attendees from the past 3 years,
extracts attendee contacts, and stores them as meeting records.
"""

import json
from datetime import datetime, timedelta, timezone

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
    fernet = _get_fernet()
    return json.loads(fernet.decrypt(encrypted.encode()).decode())


def encrypt_tokens(token_data: dict) -> str:
    fernet = _get_fernet()
    return fernet.encrypt(json.dumps(token_data).encode()).decode()


async def refresh_access_token(refresh_token: str) -> dict:
    """Refresh a Microsoft OAuth2 access token."""
    token_url = MS_TOKEN_URL.format(tenant=settings.MICROSOFT_TENANT_ID)
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            token_url,
            data={
                "client_id": settings.MICROSOFT_CLIENT_ID,
                "client_secret": settings.MICROSOFT_CLIENT_SECRET,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
                "scope": "Calendars.Read offline_access",
            },
        )
        resp.raise_for_status()
        return resp.json()


async def get_valid_access_token(encrypted_tokens: str) -> tuple[str, str]:
    """Decrypt, refresh, and return (access_token, re-encrypted blob)."""
    tokens = decrypt_tokens(encrypted_tokens)
    new_tokens = await refresh_access_token(tokens.get("refresh_token", ""))
    tokens["access_token"] = new_tokens["access_token"]
    if "refresh_token" in new_tokens:
        tokens["refresh_token"] = new_tokens["refresh_token"]
    return tokens["access_token"], encrypt_tokens(tokens)


# ── Event fetching ───────────────────────────────────────────────────────


def _extract_attendee_contacts(event: dict) -> list[dict]:
    """Extract contact dicts from a Graph API calendar event."""
    contacts: list[dict] = []
    for attendee in event.get("attendees", []):
        addr = attendee.get("emailAddress", {})
        email = addr.get("address", "").lower()
        if email and "@" in email:
            contacts.append({
                "full_name": addr.get("name", email.split("@")[0]),
                "email": email,
            })
    return contacts


async def fetch_events(
    access_token: str,
    start_date: datetime,
    end_date: datetime | None = None,
    skip: int = 0,
    top: int = 100,
) -> dict:
    """
    Fetch a page of calendar events from the user's default calendar
    via the Microsoft Graph API calendarView endpoint.
    """
    if end_date is None:
        end_date = datetime.now(timezone.utc)

    params: dict[str, str | int] = {
        "$top": top,
        "$skip": skip,
        "$select": "id,subject,start,end,attendees,bodyPreview,organizer",
        "$orderby": "start/dateTime",
        "startDateTime": start_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "endDateTime": end_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{GRAPH_API_BASE}/me/calendarView",
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
    Full sync of calendar events for the past 3 years.

    Returns:
        (contacts, meetings, updated_encrypted_tokens)
    """
    access_token, updated_tokens = await get_valid_access_token(encrypted_tokens)
    start_date = datetime.now(timezone.utc) - timedelta(days=SYNC_WINDOW_YEARS * 365)

    all_contacts: list[dict] = []
    all_meetings: list[dict] = []
    skip = 0

    while True:
        result = await fetch_events(access_token, start_date, skip=skip)
        events = result.get("value", [])
        if not events:
            break

        for event in events:
            contacts = _extract_attendee_contacts(event)
            all_contacts.extend(contacts)

            start_dt = event.get("start", {}).get("dateTime")

            all_meetings.append({
                "subject": event.get("subject", ""),
                "date": start_dt,
                "meeting_type": MeetingType.CALENDAR.value,
                "source": "outlook_calendar",
                "summary": event.get("bodyPreview", ""),
                "contacts": contacts,
            })

        if "@odata.nextLink" not in result:
            break
        skip += len(events)

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
        result = await fetch_events(access_token, last_sync_date, skip=skip)
        events = result.get("value", [])
        if not events:
            break

        for event in events:
            contacts = _extract_attendee_contacts(event)
            all_contacts.extend(contacts)

            start_dt = event.get("start", {}).get("dateTime")
            all_meetings.append({
                "subject": event.get("subject", ""),
                "date": start_dt,
                "meeting_type": MeetingType.CALENDAR.value,
                "source": "outlook_calendar",
                "summary": event.get("bodyPreview", ""),
                "contacts": contacts,
            })

        if "@odata.nextLink" not in result:
            break
        skip += len(events)

    return all_contacts, all_meetings, updated_tokens
