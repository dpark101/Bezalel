"""
Bezalel.AI — NewsFeed and NewsItem models.

Tracks RSS feed sources and their fetched articles for the dashboard.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class NewsFeed(Base):
    """An RSS feed source (e.g. WSJ, NYT, WaPo)."""

    __tablename__ = "news_feeds"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source_name: Mapped[str] = mapped_column(
        String(128), unique=True, nullable=False, index=True
    )
    rss_url: Mapped[str] = mapped_column(String(512), nullable=False)
    last_fetched: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    items: Mapped[list["NewsItem"]] = relationship(
        "NewsItem", back_populates="feed", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<NewsFeed {self.source_name}>"


class NewsItem(Base):
    """A single article fetched from an RSS feed."""

    __tablename__ = "news_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    feed_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("news_feeds.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    url: Mapped[str] = mapped_column(String(1024), nullable=False, unique=True)
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    feed: Mapped["NewsFeed"] = relationship("NewsFeed", back_populates="items")

    def __repr__(self) -> str:
        return f"<NewsItem {self.title[:40]}>"
