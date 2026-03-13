import json
import os
import ssl
import urllib.request

from services.database import (
    Database, BrainRepository, SessionRepository,
    TranscriptEntryRepository, InteractionRepository, AIResponseRepository
)
from services.updater import get_version


class SessionPackager:
    def __init__(self, db: Database):
        self._brains = BrainRepository(db)
        self._sessions = SessionRepository(db)
        self._transcripts = TranscriptEntryRepository(db)
        self._interactions = InteractionRepository(db)
        self._responses = AIResponseRepository(db)

    def package(self, session_id: str, rating: int) -> dict:
        session = self._sessions.get(session_id)
        transcripts = self._transcripts.get_by_session(session_id)
        interactions = self._interactions.get_by_session(session_id)

        duration = 0
        if session.created_at and session.ended_at:
            duration = int((session.ended_at - session.created_at).total_seconds())

        brain = self._brains.get(session.current_brain_id) if session.current_brain_id else None

        packaged_interactions = []
        for interaction in interactions:
            response = self._responses.get_by_interaction(interaction.id)
            packaged_interactions.append({
                'query': interaction.query_text,
                'query_type': interaction.query_type.value,
                'response': response.text if response else '',
                'model_used': response.model_used if response else '',
                'created_at': interaction.created_at.isoformat() if interaction.created_at else ''
            })

        return {
            'schema_version': 1,
            'app_version': get_version(),
            'rating': rating,
            'session': {
                'duration_seconds': duration,
                'template_type': brain.template_type if brain else None,
                'created_at': session.created_at.isoformat() if session.created_at else '',
                'ended_at': session.ended_at.isoformat() if session.ended_at else ''
            },
            'transcript': [
                {
                    'speaker': entry.speaker.value,
                    'text': entry.text,
                    'timestamp': entry.timestamp.isoformat() if entry.timestamp else ''
                }
                for entry in transcripts
            ],
            'interactions': packaged_interactions
        }


class FeedbackClient:
    def __init__(self, server_url: str = None):
        self._url = server_url or os.environ.get(
            'LIVEBRAIN_FEEDBACK_URL', 'https://207.211.163.42/api/feedback'
        )

    def submit(self, package: dict) -> bool:
        data = json.dumps(package).encode('utf-8')
        req = urllib.request.Request(
            self._url,
            data=data,
            headers={'Content-Type': 'application/json'},
            method='POST'
        )
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with urllib.request.urlopen(req, context=ctx) as resp:
            return 200 <= resp.status < 300
