"""
Bezalel.AI — Dashboard router.

Serves aggregated news items for the home dashboard.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database import get_db
from middleware.auth_middleware import get_current_user
from models.news import NewsFeed, NewsItem
from models.user import User

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

# ── Response schemas ─────────────────────────────────────────────────────


class NewsItemOut(BaseModel):
    id: str
    title: str
    url: str
    published_at: str | None
    summary: str | None


class NewsGroupOut(BaseModel):
    source_name: str
    items: list[NewsItemOut]


class DashboardNewsResponse(BaseModel):
    news: list[NewsGroupOut]


# ── GET /news ────────────────────────────────────────────────────────────


@router.get("/news", response_model=DashboardNewsResponse)
async def get_dashboard_news(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DashboardNewsResponse:
    """
    Return the latest news items grouped by source (e.g. WSJ, NYT, WaPo).
    Limited to 10 items per source, ordered by published date descending.
    """
    result = await db.execute(
        select(NewsFeed)
        .where(NewsFeed.active.is_(True))
        .options(selectinload(NewsFeed.items))
    )
    feeds = result.scalars().all()

    groups: list[NewsGroupOut] = []
    for feed in feeds:
        # Sort items by published_at descending, take top 10.
        sorted_items = sorted(
            feed.items,
            key=lambda item: item.published_at or item.fetched_at,
            reverse=True,
        )[:10]

        groups.append(
            NewsGroupOut(
                source_name=feed.source_name,
                items=[
                    NewsItemOut(
                        id=str(item.id),
                        title=item.title,
                        url=item.url,
                        published_at=item.published_at.isoformat() if item.published_at else None,
                        summary=item.summary,
                    )
                    for item in sorted_items
                ],
            )
        )

    return DashboardNewsResponse(news=groups)
