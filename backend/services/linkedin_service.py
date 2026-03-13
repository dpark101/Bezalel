"""
Bezalel.AI — LinkedIn CSV import and contact deduplication service.

Parses LinkedIn exported connections CSV files, maps standard fields,
and merges contacts into the Rolodex using fuzzy name matching
(rapidfuzz) to avoid duplicates.
"""

import csv
import io
import uuid
from datetime import datetime

from rapidfuzz import fuzz
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.contact import Contact

# ── Constants ────────────────────────────────────────────────────────────
# LinkedIn CSV column names (may vary by export version).
FIELD_MAP = {
    "First Name": "first_name",
    "Last Name": "last_name",
    "Email Address": "email",
    "Company": "company",
    "Position": "title",
    "Connected On": "connected_on",
}

# Fuzzy match threshold (0-100).  80+ is a strong match.
FUZZY_THRESHOLD = 80


def _parse_csv(csv_text: str) -> list[dict]:
    """
    Parse a LinkedIn connections CSV into a list of normalised dicts.

    Expected columns: First Name, Last Name, Email Address, Company,
    Position, Connected On.
    """
    reader = csv.DictReader(io.StringIO(csv_text))
    contacts: list[dict] = []

    for row in reader:
        first = (row.get("First Name") or "").strip()
        last = (row.get("Last Name") or "").strip()
        full_name = f"{first} {last}".strip()
        if not full_name:
            continue

        email = (row.get("Email Address") or "").strip().lower()
        company = (row.get("Company") or "").strip()
        title = (row.get("Position") or "").strip()
        connected_on = (row.get("Connected On") or "").strip()

        contacts.append({
            "full_name": full_name,
            "email": email if email else None,
            "company": company or None,
            "title": title or None,
            "connected_on": connected_on or None,
        })

    return contacts


def _find_fuzzy_match(
    name: str,
    email: str | None,
    existing_contacts: list[Contact],
) -> Contact | None:
    """
    Find an existing contact that matches by email or fuzzy name match.

    Priority:
      1. Exact email match (if email is available).
      2. Fuzzy name match above the threshold.
    """
    # Email-based match first.
    if email:
        for c in existing_contacts:
            if c.email_addresses and email in c.email_addresses:
                return c

    # Fuzzy name match.
    best_match: Contact | None = None
    best_score: float = 0.0

    for c in existing_contacts:
        score = fuzz.token_sort_ratio(name.lower(), c.full_name.lower())
        if score > best_score:
            best_score = score
            best_match = c

    if best_score >= FUZZY_THRESHOLD:
        return best_match

    return None


def _merge_contact(existing: Contact, new_data: dict) -> None:
    """
    Merge new LinkedIn data into an existing contact record.
    Adds email if missing, updates company/title if blank, and
    ensures ``linkedin`` is in source_tags.
    """
    # Add email if not already present.
    if new_data.get("email"):
        if existing.email_addresses is None:
            existing.email_addresses = [new_data["email"]]
        elif new_data["email"] not in existing.email_addresses:
            existing.email_addresses = existing.email_addresses + [new_data["email"]]

    # Fill in blank company / title.
    if new_data.get("company") and not existing.company:
        existing.company = new_data["company"]
    if new_data.get("title") and not existing.title:
        existing.title = new_data["title"]

    # Ensure linkedin source tag.
    if existing.source_tags is None:
        existing.source_tags = ["linkedin"]
    elif "linkedin" not in existing.source_tags:
        existing.source_tags = existing.source_tags + ["linkedin"]


async def import_linkedin_csv(
    csv_text: str,
    db: AsyncSession,
) -> tuple[int, int]:
    """
    Parse a LinkedIn CSV export and merge contacts into the database.

    Args:
        csv_text: Raw UTF-8 text of the CSV file.
        db:       Async database session.

    Returns:
        (imported_count, merged_count) — number of new vs updated contacts.
    """
    parsed = _parse_csv(csv_text)
    if not parsed:
        return 0, 0

    # Load all existing contacts for fuzzy matching.
    result = await db.execute(select(Contact))
    existing_contacts = list(result.scalars().all())

    imported = 0
    merged = 0

    for entry in parsed:
        match = _find_fuzzy_match(entry["full_name"], entry.get("email"), existing_contacts)

        if match:
            _merge_contact(match, entry)
            merged += 1
        else:
            # Create new contact.
            new_contact = Contact(
                full_name=entry["full_name"],
                email_addresses=[entry["email"]] if entry.get("email") else None,
                company=entry.get("company"),
                title=entry.get("title"),
                source_tags=["linkedin"],
            )
            db.add(new_contact)
            existing_contacts.append(new_contact)
            imported += 1

    await db.flush()
    return imported, merged


async def deduplicate_contacts(db: AsyncSession) -> int:
    """
    Run a deduplication pass across all contacts.

    Contacts are considered duplicates if:
      - They share an email address, OR
      - Their names have a fuzzy score >= FUZZY_THRESHOLD

    The contact with the earlier ``created_at`` is kept; the duplicate's
    data is merged in (emails, notes, meetings).

    Returns:
        Number of duplicates merged.
    """
    result = await db.execute(
        select(Contact).order_by(Contact.created_at.asc())
    )
    contacts = list(result.scalars().all())

    merged_ids: set[uuid.UUID] = set()
    merged_count = 0

    for i, contact_a in enumerate(contacts):
        if contact_a.id in merged_ids:
            continue

        for j in range(i + 1, len(contacts)):
            contact_b = contacts[j]
            if contact_b.id in merged_ids:
                continue

            is_duplicate = False

            # Check for shared email.
            if contact_a.email_addresses and contact_b.email_addresses:
                shared = set(contact_a.email_addresses) & set(contact_b.email_addresses)
                if shared:
                    is_duplicate = True

            # Fuzzy name match.
            if not is_duplicate:
                score = fuzz.token_sort_ratio(
                    contact_a.full_name.lower(),
                    contact_b.full_name.lower(),
                )
                if score >= FUZZY_THRESHOLD:
                    is_duplicate = True

            if is_duplicate:
                # Merge B into A: combine emails, keep A's company/title if set.
                if contact_b.email_addresses:
                    existing_emails = set(contact_a.email_addresses or [])
                    new_emails = list(existing_emails | set(contact_b.email_addresses))
                    contact_a.email_addresses = new_emails

                if contact_b.company and not contact_a.company:
                    contact_a.company = contact_b.company
                if contact_b.title and not contact_a.title:
                    contact_a.title = contact_b.title
                if contact_b.source_tags:
                    existing_tags = set(contact_a.source_tags or [])
                    contact_a.source_tags = list(existing_tags | set(contact_b.source_tags))

                # Re-assign meetings and notes from B to A.
                for meeting in getattr(contact_b, "meetings", []):
                    meeting.contact_id = contact_a.id
                for note in getattr(contact_b, "notes", []):
                    note.contact_id = contact_a.id

                await db.delete(contact_b)
                merged_ids.add(contact_b.id)
                merged_count += 1

    await db.flush()
    return merged_count
