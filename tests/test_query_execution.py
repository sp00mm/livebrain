from models import (
    Brain, BrainTool, Question, Session, TranscriptEntry, Interaction, AIResponse, ExecutionStep,
    QueryType, StepType, StepStatus, SpeakerType, ModelConfig, ToolType
)
from services.database import (
    BrainRepository, BrainToolRepository, QuestionRepository, SessionRepository,
    TranscriptEntryRepository, InteractionRepository
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

    def test_resolve_config_uses_brain_defaults(self, db):
        brain_repo = BrainRepository(db)
        config = ModelConfig(model='gpt-4o', temperature=0.5)
        brain = brain_repo.create(Brain(
            name='Test',
            default_model_config=config
        ))

        service = QueryExecutionService(db, MockEmbedder())
        ctx = QueryContext(session_id='s1', brain=brain, query_text='test')

        resolved_config = service._resolve_config(ctx)
        assert resolved_config.model == 'gpt-4o'
        assert resolved_config.temperature == 0.5

    def test_resolve_config_uses_question_override(self, db):
        brain_repo = BrainRepository(db)
        question_repo = QuestionRepository(db)

        brain = brain_repo.create(Brain(
            name='Test',
            default_model_config=ModelConfig(model='gpt-4o', temperature=0.5)
        ))

        question = question_repo.create(Question(
            brain_id=brain.id,
            text='Custom question',
            model_config_override=ModelConfig(model='gpt-4o-mini', temperature=0.2)
        ))

        service = QueryExecutionService(db, MockEmbedder())
        ctx = QueryContext(
            session_id='s1',
            brain=brain,
            query_text='test',
            query_type=QueryType.PRESET,
            question_id=question.id
        )

        resolved_config = service._resolve_config(ctx)
        assert resolved_config.model == 'gpt-4o-mini'
        assert resolved_config.temperature == 0.2

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

    def test_build_system_prompt(self, db):
        brain_repo = BrainRepository(db)
        tool_repo = BrainToolRepository(db)

        brain = brain_repo.create(Brain(name='Interview Helper', description='Helps with interviews'))
        tool_repo.create(BrainTool(brain_id=brain.id, tool_type=ToolType.SEARCH_FILES, name='Search', description='Search files'))

        service = QueryExecutionService(db, MockEmbedder())
        tools = tool_repo.get_by_brain(brain.id)
        prompt = service._build_system_prompt(brain, tools)

        assert 'Interview Helper' in prompt
        assert 'Helps with interviews' in prompt
        assert 'Search' in prompt


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
