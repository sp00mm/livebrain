import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import TranscriptEntry, SpeakerType
from services.conversation import ConversationContext


class TestConversationContext:

    def test_snapshot_creates_independent_copy(self):
        ctx = ConversationContext(session_id='s1', brain_id='b1')
        ctx.add_transcript_entries([
            TranscriptEntry(session_id='s1', speaker=SpeakerType.USER, text='Hello')
        ])
        ctx.add_qa('question 1', 'answer 1')

        snap = ctx.snapshot()

        assert len(snap.transcript_entries) == 1
        assert len(snap.qa_history) == 1

        ctx.add_qa('question 2', 'answer 2')
        assert len(ctx.qa_history) == 2
        assert len(snap.qa_history) == 1

    def test_snapshot_preserves_ids(self):
        ctx = ConversationContext(session_id='s1', brain_id='b1')
        snap = ctx.snapshot()

        assert snap.session_id == 's1'
        assert snap.brain_id == 'b1'
