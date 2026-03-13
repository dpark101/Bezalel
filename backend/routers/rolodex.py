"""
Bezalel.AI — Rolodex router.

Full CRUD for contacts, notes, AI summary generation, LinkedIn CSV
import, and deduplication.
"""

import csv
import io
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

router = APIRouter(prefix="/api/rolodex", tags=["rolodex"])

# ── Response / request schemas ───────────────────────────────────────────


class ContactBrief(BaseModel):
    id: str
    full_name: str
    email_addresses: list[str] | None
    company: str | None
    title: str | None
    source_tags: list[str] | None
    created_at: str


class NoteOut(BaseModel):
    id: str
    note_text: str
    created_at: str
    updated_at: str


class MeetingOut(BaseModel):
    id: str
    meeting_date: str | None
    meeting_type: str
    subject: str | None
    summary: str | None
    source: str | None
    created_at: str


class ContactDetail(BaseModel):
    id: str
    full_name: str
    email_addresses: list[str] | None
    phone_numbers: list[str] | None
    company: str | None
    title: str | None
    linkedin_url: str | None
    source_tags: list[str] | None
    ai_summary: dict | None
    created_at: str
    updated_at: str
    notes: list[NoteOut]
    meetings: list[MeetingOut]


class NoteCreateRequest(BaseModel):
    note_text: str


class NoteUpdateRequest(BaseModel):
    note_text: str


class ContactListResponse(BaseModel):
    contacts: list[ContactBrief]
    total: int


# ── GET /contacts ────────────────────────────────────────────────────────


@router.get("/contacts", response_model=ContactListResponse)
async def list_contacts(
    search: str | None = Query(default=None, description="Full-text search on name, email, company"),
    source: str | None = Query(default=None, description="Filter by source tag"),
    company: str | None = Query(default=None, description="Filter by company name"),
    sort_by: str = Query(default="full_name", description="Sort field: full_name, company, created_at"),
    sort_order: str = Query(default="asc", description="Sort direction: asc or desc"),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
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
                # Search within the email array by casting to text.
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

    # Apply pagination.
    query = query.offset(offset).limit(limit)
    result = await db.execute(query)
    contacts = result.scalars().all()

    return ContactListResponse(
        contacts=[
            ContactBrief(
                id=str(c.id),
                full_name=c.full_name,
                email_addresses=c.email_addresses,
                company=c.company,
                title=c.title,
                source_tags=c.source_tags,
                created_at=c.created_at.isoformat(),
            )
            for c in contacts
        ],
        total=total,
    )


# ── GET /contacts/{id} ──────────────────────────────────────────────────


@router.get("/contacts/{contact_id}", response_model=ContactDetail)
async def get_contact(
    contact_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ContactDetail:
    """Return full contact detail including notes and meetings."""
    result = await db.execute(
        select(Contact)
        .where(Contact.id == contact_id)
        .options(selectinload(Contact.notes), selectinload(Contact.meetings))
    )
    contact = result.scalar_one_or_none()
    if contact is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found")

    return ContactDetail(
        id=str(contact.id),
        full_name=contact.full_name,
        email_addresses=contact.email_addresses,
        phone_numbers=contact.phone_numbers,
        company=contact.company,
        title=contact.title,
        linkedin_url=contact.linkedin_url,
        source_tags=contact.source_tags,
        ai_summary=contact.ai_summary,
        created_at=contact.created_at.isoformat(),
        updated_at=contact.updated_at.isoformat(),
        notes=[
            NoteOut(
                id=str(n.id),
                note_text=n.note_text,
                created_at=n.created_at.isoformat(),
                updated_at=n.updated_at.isoformat(),
            )
            for n in contact.notes
        ],
        meetings=[
            MeetingOut(
                id=str(m.id),
                meeting_date=m.meeting_date.isoformat() if m.meeting_date else None,
                meeting_type=m.meeting_type.value,
                subject=m.subject,
                summary=m.summary,
                source=m.source,
                created_at=m.created_at.isoformat(),
            )
            for m in contact.meetings
        ],
    )


# ── POST /contacts/{id}/notes ───────────────────────────────────────────


@router.post("/contacts/{contact_id}/notes", response_model=NoteOut, status_code=201)
async def add_note(
    contact_id: uuid.UUID,
    body: NoteCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NoteOut:
    """Add a free-form note to a contact."""
    # Verify contact exists.
    result = await db.execute(select(Contact).where(Contact.id == contact_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found")

    note = ContactNote(contact_id=contact_id, note_text=body.note_text)
    db.add(note)
    await db.flush()
    await db.refresh(note)

    return NoteOut(
        id=str(note.id),
        note_text=note.note_text,
        created_at=note.created_at.isoformat(),
        updated_at=note.updated_at.isoformat(),
    )


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

    note.note_text = body.note_text
    await db.flush()
    await db.refresh(note)

    return NoteOut(
        id=str(note.id),
        note_text=note.note_text,
        created_at=note.created_at.isoformat(),
        updated_at=note.updated_at.isoformat(),
    )


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

    return {"message": "AI summary generated", "summary": summary}


# ── POST /import/linkedin ───────────────────────────────────────────────


@router.post("/import/linkedin")
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


# ── POST /sync/dedup ────────────────────────────────────────────────────


@router.post("/sync/dedup")
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
