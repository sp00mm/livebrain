from models import SpeakerType, FeedItemType
from services.database import Database, SessionRepository, ChatFeedItemRepository, TranscriptEntryRepository


def build_export_markdown(session_id: str, db: Database) -> str:
    session_repo = SessionRepository(db)
    feed_repo = ChatFeedItemRepository(db)
    transcript_repo = TranscriptEntryRepository(db)

    session = session_repo.get(session_id)
    entries = transcript_repo.get_by_session(session_id)
    items = feed_repo.get_by_session(session_id)

    date_str = session.created_at.strftime('%b %d, %Y  %I:%M %p')
    lines = [f'# Session - {date_str}', '', '## Transcript']

    for entry in entries:
        label = 'You' if entry.speaker == SpeakerType.USER else 'Other'
        lines.append(f'**{label}:** {entry.text}')

    qa_lines = []
    for item in items:
        if item.item_type == FeedItemType.QUESTION:
            qa_lines.append(f'**Q:** {item.content}')
        elif item.item_type == FeedItemType.ANSWER:
            qa_lines.append(f'**A:** {item.content}')

    if qa_lines:
        lines.extend(['', '## Questions & Answers'])
        lines.extend(qa_lines)

    return '\n\n'.join(lines)
