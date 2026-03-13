"""
Bezalel.AI — AI contact synthesis service.

Uses the Anthropic Claude API to generate a relationship summary for a
contact based on their meetings, notes, and profile information.

Returns a JSON-serializable dict matching the frontend ``AISummary`` type:
    contact_id, relationship_summary, key_topics,
    last_interaction_summary, suggested_next_action, generated_at
"""

import json
import logging
from datetime import datetime, timezone

import anthropic

from config import settings
from models.contact import Contact

logger = logging.getLogger(__name__)

# ── Prompt template ──────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are Bezalel, an AI assistant that helps a professional manage their \
personal network.  Given a contact profile, their interaction history \
(meetings, emails, messages), and any user notes, produce a concise \
relationship summary.

Respond with ONLY valid JSON matching this schema — no markdown fences:
{
  "relationship_summary": "<2-3 sentence overview of the relationship>",
  "key_topics": ["<topic1>", "<topic2>", ...],
  "last_interaction_summary": "<1-2 sentence summary of most recent interaction>",
  "suggested_next_action": "<one actionable suggestion to strengthen the relationship>"
}
"""


def _build_user_prompt(contact: Contact) -> str:
    """Assemble the user-facing prompt from contact data."""
    parts: list[str] = []

    # Profile
    parts.append(f"## Contact: {contact.full_name}")
    if contact.company:
        parts.append(f"Company: {contact.company}")
    if contact.title:
        parts.append(f"Title: {contact.title}")
    if contact.email_addresses:
        parts.append(f"Emails: {', '.join(contact.email_addresses)}")
    if contact.source_tags:
        parts.append(f"Sources: {', '.join(contact.source_tags)}")

    # Notes
    if contact.notes:
        parts.append("\n## User Notes")
        for note in contact.notes:
            parts.append(f"- [{note.created_at.strftime('%Y-%m-%d')}] {note.note_text}")

    # Meetings / interactions
    if contact.meetings:
        parts.append("\n## Interaction History")
        # Sort most recent first, cap at 20 to stay within token budget.
        sorted_meetings = sorted(
            contact.meetings,
            key=lambda m: m.meeting_date or m.created_at,
            reverse=True,
        )[:20]
        for m in sorted_meetings:
            date_str = (m.meeting_date or m.created_at).strftime("%Y-%m-%d")
            line = f"- [{date_str}] ({m.meeting_type.value})"
            if m.subject:
                line += f" {m.subject}"
            if m.summary:
                line += f" — {m.summary}"
            parts.append(line)

    if not contact.notes and not contact.meetings:
        parts.append(
            "\nNo interaction history or notes recorded yet. "
            "Provide a summary based on the profile information alone."
        )

    return "\n".join(parts)


# ── Public API ───────────────────────────────────────────────────────────

async def generate_ai_summary(contact: Contact) -> dict:
    """
    Call Claude to synthesize a relationship summary for *contact*.

    Returns a dict matching the frontend ``AISummary`` interface.
    If the API key is not configured or the call fails, returns a
    graceful fallback dict.
    """
    if not settings.ANTHROPIC_API_KEY:
        logger.warning("ANTHROPIC_API_KEY not set — returning placeholder summary")
        return _fallback_summary(contact)

    try:
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=512,
            system=SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": _build_user_prompt(contact)},
            ],
        )

        raw_text = message.content[0].text
        parsed = json.loads(raw_text)

        return {
            "contact_id": str(contact.id),
            "relationship_summary": parsed.get("relationship_summary", ""),
            "key_topics": parsed.get("key_topics", []),
            "last_interaction_summary": parsed.get("last_interaction_summary", ""),
            "suggested_next_action": parsed.get("suggested_next_action", ""),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    except json.JSONDecodeError:
        logger.error("Claude returned non-JSON response for contact %s", contact.id)
        return _fallback_summary(contact)
    except Exception:
        logger.exception("AI summary generation failed for contact %s", contact.id)
        return _fallback_summary(contact)


def _fallback_summary(contact: Contact) -> dict:
    """Return a minimal summary when AI generation is unavailable."""
    return {
        "contact_id": str(contact.id),
        "relationship_summary": f"Contact profile for {contact.full_name}.",
        "key_topics": [],
        "last_interaction_summary": "No AI analysis available at this time.",
        "suggested_next_action": "Connect your Anthropic API key to enable AI summaries.",
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
