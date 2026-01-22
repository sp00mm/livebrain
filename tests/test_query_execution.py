from unittest.mock import Mock, patch
from models import (
    Brain, Question, Session, TranscriptEntry, Interaction, AIResponse, ExecutionStep,
    QueryType, StepType, StepStatus, SpeakerType, ModelConfig, BrainCapabilities
)
from services.database import (
    BrainRepository, QuestionRepository, SessionRepository,
    TranscriptEntryRepository, InteractionRepository
)
from services.query_execution import QueryExecutionService, QueryContext, ExecutionCallbacks


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

    def test_resolve_config_uses_brain_defaults(self, db):
        brain_repo = BrainRepository(db)
        config = ModelConfig(model='gpt-4o', temperature=0.5)
        capabilities = BrainCapabilities(files=True, conversation=True)
        brain = brain_repo.create(Brain(
            name='Test',
            default_model_config=config,
            capabilities=capabilities
        ))

        service = QueryExecutionService(db, MockEmbedder())
        ctx = QueryContext(session_id='s1', brain=brain, query_text='test')

        resolved_config, resolved_caps = service._resolve_config(ctx)
        assert resolved_config.model == 'gpt-4o'
        assert resolved_config.temperature == 0.5
        assert resolved_caps.files is True

    def test_resolve_config_uses_question_override(self, db):
        brain_repo = BrainRepository(db)
        question_repo = QuestionRepository(db)

        brain = brain_repo.create(Brain(
            name='Test',
            default_model_config=ModelConfig(model='gpt-4o', temperature=0.5),
            capabilities=BrainCapabilities(files=True, conversation=True)
        ))

        question = question_repo.create(Question(
            brain_id=brain.id,
            text='Custom question',
            model_config_override=ModelConfig(model='gpt-4o-mini', temperature=0.2),
            capabilities_override=BrainCapabilities(files=False, conversation=True)
        ))

        service = QueryExecutionService(db, MockEmbedder())
        ctx = QueryContext(
            session_id='s1',
            brain=brain,
            query_text='test',
            query_type=QueryType.PRESET,
            question_id=question.id
        )

        resolved_config, resolved_caps = service._resolve_config(ctx)
        assert resolved_config.model == 'gpt-4o-mini'
        assert resolved_config.temperature == 0.2
        assert resolved_caps.files is False

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

    def test_gather_transcript(self, db):
        session_repo = SessionRepository(db)
        transcript_repo = TranscriptEntryRepository(db)

        session = session_repo.create(Session(name='Session'))
        transcript_repo.create(TranscriptEntry(
            session_id=session.id,
            speaker=SpeakerType.USER,
            text='Hello there'
        ))
        transcript_repo.create(TranscriptEntry(
            session_id=session.id,
            speaker=SpeakerType.OTHER,
            text='Hi, how are you?'
        ))

        service = QueryExecutionService(db, MockEmbedder())
        text, ids = service._gather_transcript(session.id)

        assert 'user: Hello there' in text
        assert 'other: Hi, how are you?' in text
        assert len(ids) == 2

    def test_build_messages_with_transcript(self, db):
        service = QueryExecutionService(db, MockEmbedder())
        messages = service._build_messages(
            query='What should I ask?',
            transcript='user: Hello\nother: Hi there',
            rag_context=''
        )

        assert len(messages) == 1
        assert messages[0].role == 'user'
        assert 'Conversation transcript:' in messages[0].content
        assert 'user: Hello' in messages[0].content
        assert 'Question: What should I ask?' in messages[0].content

    def test_build_messages_with_rag(self, db):
        service = QueryExecutionService(db, MockEmbedder())
        messages = service._build_messages(
            query='Find the policy',
            transcript='',
            rag_context='[PTO Policy]\nVacation days are...'
        )

        assert len(messages) == 1
        assert 'Relevant documents:' in messages[0].content
        assert 'PTO Policy' in messages[0].content

    def test_build_system_prompt(self, db):
        service = QueryExecutionService(db, MockEmbedder())
        brain = Brain(name='Interview Helper', description='Helps with interviews')

        prompt = service._build_system_prompt(brain)
        assert 'Interview Helper' in prompt
        assert 'Helps with interviews' in prompt


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
