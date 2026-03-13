"""
Bezalel.AI — Model package.

Imports every ORM model so that ``Base.metadata`` is fully populated
when Alembic or the application starts up.
"""

from models.contact import Contact, ContactNote, Meeting, MeetingType  # noqa: F401
from models.news import NewsFeed, NewsItem  # noqa: F401
from models.user import Session, User  # noqa: F401
