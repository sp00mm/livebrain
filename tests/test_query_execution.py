import os
import tempfile

from models import (
    Brain, Question, Session, TranscriptEntry, Interaction, AIResponse, ExecutionStep,
    Resource, ResourceType,
    QueryType, StepType, StepStatus, SpeakerType
)
from services.database import (
    BrainRepository, QuestionRepository, SessionRepository,
    TranscriptEntryRepository, InteractionRepository, ResourceRepository
)
from services.query_execution import QueryExecutionService, QueryContext, ExecutionCallbacks
from services.conversation import ConversationContext


class MockEmbedder:
    def embed(self, text, is_query=True):
        return [0.0] * 768


class TestQueryContext:
    def test_dataclass(self):
        brain = Brain(name='Test')
        ctx = QueryContext(
            session_id='sess-1',
            brain=brain,
            query_text='What is this?'
        )
        assert ctx.session_id == 'sess-1'
        assert ctx.brain == brain
        assert ctx.query_text == 'What is this?'
        assert ctx.query_type == QueryType.FREEFORM
        assert ctx.question_id is None

    def test_preset_query(self):
        brain = Brain(name='Test')
        ctx = QueryContext(
            session_id='sess-1',
            brain=brain,
            query_text='Analyze this',
            query_type=QueryType.PRESET,
            question_id='q-1'
        )
        assert ctx.query_type == QueryType.PRESET
        assert ctx.question_id == 'q-1'


class TestExecutionCallbacks:
    def test_dataclass(self):
        callbacks = ExecutionCallbacks(
            on_step=lambda s: None,
            on_delta=lambda d: None,
            on_complete=lambda r: None
        )
        assert callable(callbacks.on_step)
        assert callable(callbacks.on_delta)
        assert callable(callbacks.on_complete)


class TestQueryExecutionService:
    def test_init(self, db):
        service = QueryExecutionService(db, MockEmbedder())
        assert service.db == db
        assert service.embedder is not None

    def test_create_interaction(self, db):
        brain_repo = BrainRepository(db)
        session_repo = SessionRepository(db)

        brain = brain_repo.create(Brain(name='Test'))
        session = session_repo.create(Session(name='Session'))

        service = QueryExecutionService(db, MockEmbedder())
        ctx = QueryContext(
            session_id=session.id,
            brain=brain,
            query_text='What is this about?'
        )

        interaction = service._create_interaction(ctx)
        assert interaction.id is not None
        assert interaction.session_id == session.id
        assert interaction.brain_id == brain.id
        assert interaction.query_text == 'What is this about?'
        assert interaction.query_type == QueryType.FREEFORM

    def test_build_system_prompt_default(self, db):
        service = QueryExecutionService(db, MockEmbedder())
        brain = Brain(name='Interview Helper', description='Helps with interviews')

        prompt = service._build_system_prompt(brain)

        assert 'Interview Helper' in prompt
        assert 'Helps with interviews' in prompt

    def test_build_system_prompt_custom(self, db):
        service = QueryExecutionService(db, MockEmbedder())
        brain = Brain(name='Test', system_prompt='You are a custom assistant.')

        prompt = service._build_system_prompt(brain)

        assert prompt == 'You are a custom assistant.'


class TestConversationContext:
    def test_build_messages_empty(self):
        ctx = ConversationContext(session_id='s1', brain_id='b1')
        messages = ctx.build_messages()
        assert len(messages) == 0

    def test_build_messages_with_transcript(self):
        ctx = ConversationContext(session_id='s1', brain_id='b1')
        ctx.transcript_entries = [
            TranscriptEntry(session_id='s1', speaker=SpeakerType.USER, text='Hello'),
            TranscriptEntry(session_id='s1', speaker=SpeakerType.OTHER, text='Hi there')
        ]

        messages = ctx.build_messages()
        assert len(messages) == 1
        assert '[Live Transcript]' in messages[0].content
        assert 'You: Hello' in messages[0].content
        assert 'Them: Hi there' in messages[0].content

    def test_build_messages_with_qa_history(self):
        ctx = ConversationContext(session_id='s1', brain_id='b1')
        ctx.add_qa('What is this?', 'This is a test.')

        messages = ctx.build_messages()
        assert len(messages) == 2
        assert messages[0].role == 'user'
        assert messages[0].content == 'What is this?'
        assert messages[1].role == 'assistant'
        assert messages[1].content == 'This is a test.'

    def test_get_transcript_text(self):
        ctx = ConversationContext(session_id='s1', brain_id='b1')
        ctx.transcript_entries = [
            TranscriptEntry(session_id='s1', speaker=SpeakerType.USER, text='Hello'),
            TranscriptEntry(session_id='s1', speaker=SpeakerType.OTHER, text='Hi')
        ]

        text = ctx.get_transcript_text()
        assert 'You: Hello' in text
        assert 'Them: Hi' in text


class TestQueryExecutionServiceIntegration:
    def test_emit_and_complete_step(self, db):
        brain_repo = BrainRepository(db)
        session_repo = SessionRepository(db)
        interaction_repo = InteractionRepository(db)

        brain = brain_repo.create(Brain(name='Test'))
        session = session_repo.create(Session(name='Session'))
        interaction = interaction_repo.create(Interaction(
            session_id=session.id,
            brain_id=brain.id,
            query_text='test'
        ))

        steps_received = []
        service = QueryExecutionService(db, MockEmbedder())
        step = service._emit_step(
            interaction.id,
            StepType.SEARCHING_FILES,
            lambda s: steps_received.append(s)
        )

        assert step.step_type == StepType.SEARCHING_FILES
        assert step.status == StepStatus.IN_PROGRESS
        assert len(steps_received) == 1

        service._complete_step(step.id, lambda s: steps_received.append(s))
        assert len(steps_received) == 2
        assert steps_received[1].status == StepStatus.COMPLETED


class TestBuildSystemPromptWithFileContext:
    def test_default_prompt_with_file_context(self, db):
        service = QueryExecutionService(db, MockEmbedder())
        brain = Brain(name='Interview Helper', description='Helps with interviews')

        prompt = service._build_system_prompt(brain, 'some file content')

        assert 'Interview Helper' in prompt
        assert 'Helps with interviews' in prompt
        assert 'Here are reference documents' in prompt
        assert 'some file content' in prompt

    def test_custom_prompt_with_file_context(self, db):
        service = QueryExecutionService(db, MockEmbedder())
        brain = Brain(name='Test', system_prompt='You are a custom assistant.')

        prompt = service._build_system_prompt(brain, 'doc text')

        assert prompt.startswith('You are a custom assistant.')
        assert 'Here are reference documents' in prompt
        assert 'doc text' in prompt

    def test_empty_file_context_not_appended(self, db):
        service = QueryExecutionService(db, MockEmbedder())
        brain = Brain(name='Test', description='A test brain')

        prompt = service._build_system_prompt(brain, '')

        assert 'reference documents' not in prompt


class TestGatherFileContext:
    def test_gather_text_files(self, db):
        brain_repo = BrainRepository(db)
        resource_repo = ResourceRepository(db)
        brain = brain_repo.create(Brain(name='Test'))

        with tempfile.NamedTemporaryFile(suffix='.txt', mode='w', delete=False) as f:
            f.write('Hello from test file')
            tmp_path = f.name

        resource = resource_repo.create(Resource(
            resource_type=ResourceType.FILE, name='test.txt', path=tmp_path
        ))
        resource_repo.link_to_brain(resource.id, brain.id)

        service = QueryExecutionService(db, MockEmbedder())
        result = service._gather_file_context(brain.id)

        assert 'Hello from test file' in result
        os.unlink(tmp_path)

    def test_gather_skips_images(self, db):
        brain_repo = BrainRepository(db)
        resource_repo = ResourceRepository(db)
        brain = brain_repo.create(Brain(name='Test'))

        resource = resource_repo.create(Resource(
            resource_type=ResourceType.FILE, name='photo.png', path='/fake/image.png'
        ))
        resource_repo.link_to_brain(resource.id, brain.id)

        service = QueryExecutionService(db, MockEmbedder())
        result = service._gather_file_context(brain.id)

        assert result == ''

    def test_gather_multiple_files(self, db):
        brain_repo = BrainRepository(db)
        resource_repo = ResourceRepository(db)
        brain = brain_repo.create(Brain(name='Test'))

        paths = []
        for i, content in enumerate(['First file content', 'Second file content']):
            with tempfile.NamedTemporaryFile(suffix='.txt', mode='w', delete=False) as f:
                f.write(content)
                paths.append(f.name)
            resource = resource_repo.create(Resource(
                resource_type=ResourceType.FILE, name=f'file{i}.txt', path=f.name
            ))
            resource_repo.link_to_brain(resource.id, brain.id)

        service = QueryExecutionService(db, MockEmbedder())
        result = service._gather_file_context(brain.id)

        assert 'First file content' in result
        assert 'Second file content' in result
        assert '---' in result

        for p in paths:
            os.unlink(p)
