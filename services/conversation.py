from dataclasses import dataclass, field
from typing import Optional

from models import TranscriptEntry, SpeakerType
from services.llm.interfaces import Message


@dataclass
class QAPair:
    question: str
    answer: str


@dataclass
class ConversationContext:
    session_id: str
    brain_id: str
    transcript_entries: list[TranscriptEntry] = field(default_factory=list)
    qa_history: list[QAPair] = field(default_factory=list)

    def add_transcript_entries(self, entries: list[TranscriptEntry]) -> None:
        existing_ids = {e.id for e in self.transcript_entries}
        for entry in entries:
            if entry.id not in existing_ids:
                self.transcript_entries.append(entry)

    def add_qa(self, question: str, answer: str) -> None:
        self.qa_history.append(QAPair(question=question, answer=answer))

    def build_messages(self) -> list[Message]:
        messages = []

        if self.transcript_entries:
            transcript_text = self.get_transcript_text()
            messages.append(Message(
                role='user',
                content=f'[Live Transcript]\n{transcript_text}'
            ))

        for qa in self.qa_history:
            messages.append(Message(role='user', content=qa.question))
            messages.append(Message(role='assistant', content=qa.answer))

        return messages

    def get_transcript_text(self) -> str:
        lines = []
        for entry in self.transcript_entries:
            speaker = 'You' if entry.speaker == SpeakerType.USER else 'Them'
            lines.append(f'{speaker}: {entry.text}')
        return '\n'.join(lines)

    def get_transcript_ids(self) -> list[str]:
        return [e.id for e in self.transcript_entries]


class ConversationContextCache:
    def __init__(self):
        self._contexts: dict[tuple[str, str], ConversationContext] = {}

    def get(self, session_id: str, brain_id: str) -> ConversationContext:
        key = (session_id, brain_id)
        if key not in self._contexts:
            self._contexts[key] = ConversationContext(session_id=session_id, brain_id=brain_id)
        return self._contexts[key]

    def clear(self, session_id: Optional[str] = None) -> None:
        if session_id:
            keys_to_remove = [k for k in self._contexts if k[0] == session_id]
            for key in keys_to_remove:
                del self._contexts[key]
        else:
            self._contexts.clear()
