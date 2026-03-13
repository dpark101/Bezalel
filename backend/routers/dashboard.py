"""
Bezalel.AI — News feeds router.

Serves aggregated news items for the home dashboard.
Frontend fetches ``GET /api/news/feeds``.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database import get_db
from middleware.auth_middleware import get_current_user
from models.news import NewsFeed, NewsItem
from models.user import User

router = APIRouter(prefix="/api/news", tags=["news"])


# ── GET /feeds ───────────────────────────────────────────────────────────


@router.get("/feeds")
async def get_news_feeds(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
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

    output: list[dict] = []
    for feed in feeds:
        # Sort items by published_at descending, take top 10.
        sorted_items = sorted(
            feed.items,
            key=lambda item: item.published_at or item.fetched_at,
            reverse=True,
        )[:10]

        output.append({
            "source": feed.source_name,
            "items": [
                {
                    "id": str(item.id),
                    "title": item.title,
                    "url": item.url,
                    "published_at": item.published_at.isoformat() if item.published_at else None,
                    "summary": item.summary,
                }
                for item in sorted_items
            ],
            "last_updated": feed.last_fetched.isoformat() if feed.last_fetched else None,
        })

    return output
