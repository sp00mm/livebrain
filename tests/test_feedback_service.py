import json
import os
import sys
from datetime import datetime, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import (
    Brain, Session, TranscriptEntry, Interaction, AIResponse,
    SpeakerType, QueryType
)
from services.database import (
    BrainRepository, SessionRepository, TranscriptEntryRepository,
    InteractionRepository, AIResponseRepository
)
from services.feedback_service import SessionPackager, FeedbackClient


class TestSessionPackager:

    def _create_session_data(self, db):
        brain_repo = BrainRepository(db)
        session_repo = SessionRepository(db)
        transcript_repo = TranscriptEntryRepository(db)
        interaction_repo = InteractionRepository(db)
        response_repo = AIResponseRepository(db)

        brain = Brain(name='Interview', template_type='interview')
        brain_repo.create(brain)

        start = datetime(2026, 3, 13, 10, 0, 0)
        end = datetime(2026, 3, 13, 10, 5, 0)
        session = Session(
            current_brain_id=brain.id,
            created_at=start,
            ended_at=end
        )
        session_repo.create(session)

        transcript_repo.create(TranscriptEntry(
            session_id=session.id,
            speaker=SpeakerType.USER,
            text='Hello there',
            timestamp=start
        ))
        transcript_repo.create(TranscriptEntry(
            session_id=session.id,
            speaker=SpeakerType.OTHER,
            text='Hi, nice to meet you',
            timestamp=start + timedelta(seconds=5)
        ))

        interaction = Interaction(
            session_id=session.id,
            brain_id=brain.id,
            query_type=QueryType.FREEFORM,
            query_text='What was discussed?',
            created_at=start + timedelta(seconds=30)
        )
        interaction_repo.create(interaction)

        response_repo.create(AIResponse(
            interaction_id=interaction.id,
            text='They exchanged greetings.',
            model_used='gpt-5-chat-latest'
        ))

        return session.id

    def test_package_structure(self, db):
        session_id = self._create_session_data(db)
        packager = SessionPackager(db)

        package = packager.package(session_id, rating=1)

        assert package['schema_version'] == 1
        assert package['rating'] == 1
        assert 'app_version' in package

    def test_package_session_info(self, db):
        session_id = self._create_session_data(db)
        packager = SessionPackager(db)

        package = packager.package(session_id, rating=1)

        assert package['session']['duration_seconds'] == 300
        assert package['session']['template_type'] == 'interview'

    def test_package_transcript(self, db):
        session_id = self._create_session_data(db)
        packager = SessionPackager(db)

        package = packager.package(session_id, rating=1)

        assert len(package['transcript']) == 2
        assert package['transcript'][0]['speaker'] == 'user'
        assert package['transcript'][0]['text'] == 'Hello there'
        assert package['transcript'][1]['speaker'] == 'other'

    def test_package_interactions(self, db):
        session_id = self._create_session_data(db)
        packager = SessionPackager(db)

        package = packager.package(session_id, rating=1)

        assert len(package['interactions']) == 1
        assert package['interactions'][0]['query'] == 'What was discussed?'
        assert package['interactions'][0]['query_type'] == 'freeform'
        assert package['interactions'][0]['response'] == 'They exchanged greetings.'
        assert package['interactions'][0]['model_used'] == 'gpt-5-chat-latest'

    def test_package_no_brain(self, db):
        session_repo = SessionRepository(db)
        session = Session(created_at=datetime(2026, 3, 13, 10, 0, 0))
        session_repo.create(session)

        packager = SessionPackager(db)
        package = packager.package(session.id, rating=0)

        assert package['session']['template_type'] is None

    def test_package_is_json_serializable(self, db):
        session_id = self._create_session_data(db)
        packager = SessionPackager(db)

        package = packager.package(session_id, rating=1)
        serialized = json.dumps(package)

        assert isinstance(serialized, str)
        assert json.loads(serialized) == package


class TestFeedbackClient:

    def test_default_url(self):
        client = FeedbackClient()
        assert client._url == 'https://livebrain.app/api/feedback'

    def test_custom_url(self):
        client = FeedbackClient('https://example.com/feedback')
        assert client._url == 'https://example.com/feedback'

    def test_env_url(self):
        with patch.dict(os.environ, {'LIVEBRAIN_FEEDBACK_URL': 'https://test.com/fb'}):
            client = FeedbackClient()
            assert client._url == 'https://test.com/fb'

    def test_submit_success(self):
        received = {}

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers['Content-Length'])
                received['body'] = json.loads(self.rfile.read(length))
                received['content_type'] = self.headers['Content-Type']
                self.send_response(200)
                self.end_headers()

            def log_message(self, *args):
                pass

        server = HTTPServer(('127.0.0.1', 0), Handler)
        port = server.server_address[1]
        thread = Thread(target=server.handle_request)
        thread.start()

        client = FeedbackClient(f'http://127.0.0.1:{port}/api/feedback')
        result = client.submit({'schema_version': 1, 'rating': 1})

        thread.join(timeout=5)
        server.server_close()

        assert result is True
        assert received['body'] == {'schema_version': 1, 'rating': 1}
        assert received['content_type'] == 'application/json'

    def test_submit_server_error(self):
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                self.send_response(500)
                self.end_headers()

            def log_message(self, *args):
                pass

        server = HTTPServer(('127.0.0.1', 0), Handler)
        port = server.server_address[1]
        thread = Thread(target=server.handle_request)
        thread.start()

        client = FeedbackClient(f'http://127.0.0.1:{port}/api/feedback')
        raised = False
        try:
            client.submit({'test': True})
        except Exception:
            raised = True

        thread.join(timeout=5)
        server.server_close()

        assert raised
