"""
Bezalel.AI — Contact, ContactNote, and Meeting models.

The Rolodex system stores contacts aggregated from email, calendar,
LinkedIn, and iMessage sources.  Each contact may have free-form notes
and meeting records with full-text content.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class MeetingType(str, enum.Enum):
    """Source channel for a meeting / interaction record."""

    EMAIL = "email"
    CALENDAR = "calendar"
    IMESSAGE = "imessage"


class Contact(Base):
    """
    A person in the Rolodex.

    Contacts are aggregated from multiple sources and deduplicated.
    ``ai_summary`` holds a Claude-generated JSON digest of the relationship.
    """

    __tablename__ = "contacts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    full_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    email_addresses: Mapped[list[str] | None] = mapped_column(
        ARRAY(String), nullable=True
    )
    phone_numbers: Mapped[list[str] | None] = mapped_column(
        ARRAY(String), nullable=True
    )
    company: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    linkedin_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    source_tags: Mapped[list[str] | None] = mapped_column(
        ARRAY(String), nullable=True
    )
    ai_summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    notes: Mapped[list["ContactNote"]] = relationship(
        "ContactNote", back_populates="contact", cascade="all, delete-orphan"
    )
    meetings: Mapped[list["Meeting"]] = relationship(
        "Meeting", back_populates="contact", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Contact {self.full_name}>"


class ContactNote(Base):
    """Free-form note attached to a contact."""

    __tablename__ = "contact_notes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    contact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("contacts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    note_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    contact: Mapped["Contact"] = relationship("Contact", back_populates="notes")

    def __repr__(self) -> str:
        return f"<ContactNote {self.id} contact={self.contact_id}>"


class Meeting(Base):
    """
    A recorded interaction (email thread, calendar event, or iMessage
    conversation) tied to a contact.
    """

    __tablename__ = "meetings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    contact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("contacts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    meeting_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    meeting_type: Mapped[MeetingType] = mapped_column(
        Enum(MeetingType, name="meeting_type_enum"), nullable=False
    )
    subject: Mapped[str | None] = mapped_column(String(512), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str | None] = mapped_column(String(64), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    contact: Mapped["Contact"] = relationship("Contact", back_populates="meetings")

    def __repr__(self) -> str:
        return f"<Meeting {self.id} type={self.meeting_type}>"
