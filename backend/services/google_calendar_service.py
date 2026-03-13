"""
Bezalel.AI — Google Calendar integration service.

Fetches calendar events with attendees from the past 3 years,
extracts attendee contacts, and creates meeting records.
"""

import json
from datetime import datetime, timedelta, timezone

import httpx
from cryptography.fernet import Fernet

from config import settings
from models.contact import MeetingType

# ── Constants ────────────────────────────────────────────────────────────
CALENDAR_API_BASE = "https://www.googleapis.com/calendar/v3"
SYNC_WINDOW_YEARS = 3


# ── Token helpers (shared pattern with gmail_service) ────────────────────


def _get_fernet() -> Fernet:
    return Fernet(settings.ENCRYPTION_KEY.encode())


def decrypt_tokens(encrypted: str) -> dict:
    fernet = _get_fernet()
    return json.loads(fernet.decrypt(encrypted.encode()).decode())


def encrypt_tokens(token_data: dict) -> str:
    fernet = _get_fernet()
    return fernet.encrypt(json.dumps(token_data).encode()).decode()


async def refresh_access_token(refresh_token: str) -> dict:
    """Refresh a Google OAuth2 access token."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://oauth2.googleapis.com/token",
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
    """Decrypt, refresh, and return (access_token, re-encrypted blob)."""
    tokens = decrypt_tokens(encrypted_tokens)
    new_tokens = await refresh_access_token(tokens.get("refresh_token", ""))
    tokens["access_token"] = new_tokens["access_token"]
    return tokens["access_token"], encrypt_tokens(tokens)


# ── Event fetching ───────────────────────────────────────────────────────


def _extract_attendee_contacts(event: dict) -> list[dict]:
    """Extract contact dicts from a calendar event's attendee list."""
    contacts: list[dict] = []
    for attendee in event.get("attendees", []):
        email = attendee.get("email", "").lower()
        if email and "@" in email:
            contacts.append({
                "full_name": attendee.get("displayName", email.split("@")[0]),
                "email": email,
            })
    return contacts


def _parse_event_datetime(dt_obj: dict) -> str | None:
    """
    Parse a Google Calendar dateTime or date field into an ISO string.
    """
    return dt_obj.get("dateTime") or dt_obj.get("date")


async def fetch_events(
    access_token: str,
    time_min: datetime,
    page_token: str | None = None,
    max_results: int = 250,
) -> dict:
    """
    Fetch a page of calendar events from the user's primary calendar.
    """
    params: dict[str, str | int] = {
        "maxResults": max_results,
        "singleEvents": "true",
        "orderBy": "startTime",
        "timeMin": time_min.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    if page_token:
        params["pageToken"] = page_token

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{CALENDAR_API_BASE}/calendars/primary/events",
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
    Fetch all calendar events with attendees from the past 3 years.

    Returns:
        (contacts, meetings, updated_encrypted_tokens)
    """
    access_token, updated_tokens = await get_valid_access_token(encrypted_tokens)
    time_min = datetime.now(timezone.utc) - timedelta(days=SYNC_WINDOW_YEARS * 365)

    all_contacts: list[dict] = []
    all_meetings: list[dict] = []
    page_token: str | None = None

    while True:
        result = await fetch_events(access_token, time_min, page_token=page_token)
        events = result.get("items", [])

        for event in events:
            contacts = _extract_attendee_contacts(event)
            all_contacts.extend(contacts)

            start = _parse_event_datetime(event.get("start", {}))

            all_meetings.append({
                "subject": event.get("summary", ""),
                "date": start,
                "meeting_type": MeetingType.CALENDAR.value,
                "source": "google_calendar",
                "summary": event.get("description", ""),
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
    Incremental sync: only fetch events updated since ``last_sync_date``.
    """
    access_token, updated_tokens = await get_valid_access_token(encrypted_tokens)

    all_contacts: list[dict] = []
    all_meetings: list[dict] = []
    page_token: str | None = None

    while True:
        # Use updatedMin for incremental sync.
        params: dict[str, str | int] = {
            "maxResults": 250,
            "singleEvents": "true",
            "orderBy": "startTime",
            "timeMin": last_sync_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        if page_token:
            params["pageToken"] = page_token

        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{CALENDAR_API_BASE}/calendars/primary/events",
                headers={"Authorization": f"Bearer {access_token}"},
                params=params,
                timeout=30.0,
            )
            resp.raise_for_status()
            result = resp.json()

        events = result.get("items", [])
        for event in events:
            contacts = _extract_attendee_contacts(event)
            all_contacts.extend(contacts)

            start = _parse_event_datetime(event.get("start", {}))
            all_meetings.append({
                "subject": event.get("summary", ""),
                "date": start,
                "meeting_type": MeetingType.CALENDAR.value,
                "source": "google_calendar",
                "summary": event.get("description", ""),
                "contacts": contacts,
            })

        page_token = result.get("nextPageToken")
        if not page_token:
            break

    return all_contacts, all_meetings, updated_tokens
