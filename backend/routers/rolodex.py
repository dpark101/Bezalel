"""
Bezalel.AI — Rolodex router.

Full CRUD for contacts, notes, AI summary generation, LinkedIn CSV
import, and deduplication.

Routes are mounted at ``/api`` so contact endpoints resolve to
``/api/contacts/...`` matching the frontend API client.
"""

import math
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database import get_db
from middleware.auth_middleware import get_current_user
from models.contact import Contact, ContactNote, Meeting
from models.user import User
from services.ai_synthesis_service import generate_ai_summary
from services.linkedin_service import import_linkedin_csv, deduplicate_contacts

router = APIRouter(prefix="/api", tags=["rolodex"])

# ── Response / request schemas ───────────────────────────────────────────


class ContactBrief(BaseModel):
    id: str
    name: str
    email: str | None
    emails: list[str]
    phone: str | None
    phones: list[str]
    company: str | None
    title: str | None
    linkedin_url: str | None
    sources: list[str]
    created_at: str
    updated_at: str


class NoteOut(BaseModel):
    id: str
    contact_id: str
    content: str
    created_at: str
    updated_at: str


class MeetingOut(BaseModel):
    id: str
    contact_id: str
    title: str | None
    date: str | None
    type: str
    summary: str | None
    source: str | None
    created_at: str


class ContactDetail(BaseModel):
    id: str
    name: str
    email: str | None
    emails: list[str]
    phone: str | None
    phones: list[str]
    company: str | None
    title: str | None
    linkedin_url: str | None
    sources: list[str]
    ai_summary: dict | None
    created_at: str
    updated_at: str


class NoteCreateRequest(BaseModel):
    content: str


class NoteUpdateRequest(BaseModel):
    content: str


class ContactListResponse(BaseModel):
    items: list[ContactBrief]
    total_pages: int
    companies: list[str]


# ── Helpers ──────────────────────────────────────────────────────────────


def _contact_brief(c: Contact) -> ContactBrief:
    """Map a Contact ORM object to the frontend-friendly brief schema."""
    emails = c.email_addresses or []
    phones = c.phone_numbers or []
    return ContactBrief(
        id=str(c.id),
        name=c.full_name,
        email=emails[0] if emails else None,
        emails=emails,
        phone=phones[0] if phones else None,
        phones=phones,
        company=c.company,
        title=c.title,
        linkedin_url=c.linkedin_url,
        sources=c.source_tags or [],
        created_at=c.created_at.isoformat(),
        updated_at=c.updated_at.isoformat(),
    )


def _note_out(n: ContactNote) -> NoteOut:
    return NoteOut(
        id=str(n.id),
        contact_id=str(n.contact_id),
        content=n.note_text,
        created_at=n.created_at.isoformat(),
        updated_at=n.updated_at.isoformat(),
    )


def _meeting_out(m: Meeting) -> MeetingOut:
    return MeetingOut(
        id=str(m.id),
        contact_id=str(m.contact_id),
        title=m.subject,
        date=(m.meeting_date or m.created_at).isoformat(),
        type=m.meeting_type.value,
        summary=m.summary,
        source=m.source,
        created_at=m.created_at.isoformat(),
    )


# ── GET /contacts ────────────────────────────────────────────────────────


@router.get("/contacts", response_model=ContactListResponse)
async def list_contacts(
    search: str | None = Query(default=None),
    source: str | None = Query(default=None),
    company: str | None = Query(default=None),
    sort_by: str = Query(default="full_name"),
    sort_order: str = Query(default="asc"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ContactListResponse:
    """
    List contacts with optional search, filtering, sorting, and pagination.
    """
    query = select(Contact)

    # Full-text search across name, email addresses, and company.
    if search:
        pattern = f"%{search}%"
        query = query.where(
            or_(
                Contact.full_name.ilike(pattern),
                Contact.company.ilike(pattern),
                Contact.email_addresses.any(search),
            )
        )

    # Filter by source tag.
    if source:
        query = query.where(Contact.source_tags.any(source))

    # Filter by company.
    if company:
        query = query.where(Contact.company.ilike(f"%{company}%"))

    # Sorting.
    sort_column = getattr(Contact, sort_by, Contact.full_name)
    if sort_order == "desc":
        query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(sort_column.asc())

    # Get total count (without pagination).
    from sqlalchemy import func as sa_func

    count_result = await db.execute(
        select(sa_func.count()).select_from(query.subquery())
    )
    total = count_result.scalar() or 0
    total_pages = max(1, math.ceil(total / page_size))

    # Apply pagination.
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)
    result = await db.execute(query)
    contacts = result.scalars().all()

    # Collect unique companies for the filter dropdown.
    company_result = await db.execute(
        select(Contact.company)
        .where(Contact.company.is_not(None))
        .distinct()
        .order_by(Contact.company)
    )
    companies = [row[0] for row in company_result.all() if row[0]]

    return ContactListResponse(
        items=[_contact_brief(c) for c in contacts],
        total_pages=total_pages,
        companies=companies,
    )


# ── GET /contacts/{id} ──────────────────────────────────────────────────


@router.get("/contacts/{contact_id}")
async def get_contact(
    contact_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return full contact detail."""
    result = await db.execute(
        select(Contact)
        .where(Contact.id == contact_id)
        .options(selectinload(Contact.notes), selectinload(Contact.meetings))
    )
    contact = result.scalar_one_or_none()
    if contact is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found")

    emails = contact.email_addresses or []
    phones = contact.phone_numbers or []

    return {
        "id": str(contact.id),
        "name": contact.full_name,
        "email": emails[0] if emails else None,
        "emails": emails,
        "phone": phones[0] if phones else None,
        "phones": phones,
        "company": contact.company,
        "title": contact.title,
        "linkedin_url": contact.linkedin_url,
        "sources": contact.source_tags or [],
        "ai_summary": contact.ai_summary,
        "created_at": contact.created_at.isoformat(),
        "updated_at": contact.updated_at.isoformat(),
    }


# ── GET /contacts/{id}/meetings ──────────────────────────────────────────


@router.get("/contacts/{contact_id}/meetings")
async def get_contact_meetings(
    contact_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Return meetings for a contact, most recent first."""
    result = await db.execute(
        select(Contact).where(Contact.id == contact_id)
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found")

    meetings_result = await db.execute(
        select(Meeting)
        .where(Meeting.contact_id == contact_id)
        .order_by(Meeting.meeting_date.desc().nullslast(), Meeting.created_at.desc())
    )
    meetings = meetings_result.scalars().all()
    return [_meeting_out(m).model_dump() for m in meetings]


# ── GET /contacts/{id}/notes ─────────────────────────────────────────────


@router.get("/contacts/{contact_id}/notes")
async def get_contact_notes(
    contact_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Return notes for a contact, most recent first."""
    result = await db.execute(
        select(Contact).where(Contact.id == contact_id)
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found")

    notes_result = await db.execute(
        select(ContactNote)
        .where(ContactNote.contact_id == contact_id)
        .order_by(ContactNote.created_at.desc())
    )
    notes = notes_result.scalars().all()
    return [_note_out(n).model_dump() for n in notes]


# ── GET /contacts/{id}/ai-summary ────────────────────────────────────────


@router.get("/contacts/{contact_id}/ai-summary")
async def get_ai_summary(
    contact_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return the stored AI summary for a contact, or 404 if none exists."""
    result = await db.execute(
        select(Contact).where(Contact.id == contact_id)
    )
    contact = result.scalar_one_or_none()
    if contact is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found")

    if contact.ai_summary is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No AI summary available")

    return contact.ai_summary


# ── POST /contacts/{id}/notes ───────────────────────────────────────────


@router.post("/contacts/{contact_id}/notes", response_model=NoteOut, status_code=201)
async def add_note(
    contact_id: uuid.UUID,
    body: NoteCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NoteOut:
    """Add a free-form note to a contact."""
    result = await db.execute(select(Contact).where(Contact.id == contact_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found")

    note = ContactNote(contact_id=contact_id, note_text=body.content)
    db.add(note)
    await db.flush()
    await db.refresh(note)

    return _note_out(note)


# ── PUT /contacts/{id}/notes/{note_id} ──────────────────────────────────


@router.put("/contacts/{contact_id}/notes/{note_id}", response_model=NoteOut)
async def update_note(
    contact_id: uuid.UUID,
    note_id: uuid.UUID,
    body: NoteUpdateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NoteOut:
    """Update an existing note on a contact."""
    result = await db.execute(
        select(ContactNote).where(
            ContactNote.id == note_id,
            ContactNote.contact_id == contact_id,
        )
    )
    note = result.scalar_one_or_none()
    if note is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")

    note.note_text = body.content
    await db.flush()
    await db.refresh(note)

    return _note_out(note)


# ── POST /contacts/{id}/ai-summary ──────────────────────────────────────


@router.post("/contacts/{contact_id}/ai-summary")
async def trigger_ai_summary(
    contact_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Trigger AI summary generation for a contact.  Collects all meetings,
    notes, and contact info, sends to Claude, and stores the result.
    """
    result = await db.execute(
        select(Contact)
        .where(Contact.id == contact_id)
        .options(selectinload(Contact.notes), selectinload(Contact.meetings))
    )
    contact = result.scalar_one_or_none()
    if contact is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found")

    summary = await generate_ai_summary(contact)
    contact.ai_summary = summary
    await db.commit()

    return summary


# ── POST /contacts/import/linkedin ───────────────────────────────────────


@router.post("/contacts/import/linkedin")
async def import_linkedin(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Accept a LinkedIn connections CSV export, parse it, and merge
    contacts into the Rolodex.
    """
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Please upload a CSV file")

    contents = await file.read()
    text = contents.decode("utf-8-sig")  # Handle BOM in LinkedIn exports.

    imported, merged = await import_linkedin_csv(text, db)

    return {
        "message": f"Imported {imported} new contacts, merged {merged} existing.",
        "imported": imported,
        "merged": merged,
    }


# ── POST /contacts/sync/dedup ────────────────────────────────────────────


@router.post("/contacts/sync/dedup")
async def trigger_dedup(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Run a fuzzy deduplication pass across all contacts.  Merges duplicates
    based on name similarity and shared email addresses.
    """
    merged_count = await deduplicate_contacts(db)
    return {"message": f"Deduplication complete. Merged {merged_count} duplicate(s)."}
