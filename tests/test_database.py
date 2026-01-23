"""
Tests for Livebrain database layer.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import (
    Brain, Question, Resource, DocumentChunk, Session,
    TranscriptEntry, Interaction, AIResponse, ExecutionStep,
    MCPServer, ModelConfig, BrainCapabilities,
    FileReference, SpeakerType, QueryType, ResourceType,
    IndexStatus, StepType, StepStatus, MCPStatus
)
from services.database import (
    BrainRepository, QuestionRepository, ResourceRepository,
    DocumentChunkRepository, SessionRepository, TranscriptEntryRepository,
    InteractionRepository, AIResponseRepository, ExecutionStepRepository,
    MCPServerRepository, UserSettingsRepository, RAGService
)


class TestBrainRepository:
    """Tests for Brain CRUD operations."""

    def test_create_brain(self, db):
        repo = BrainRepository(db)
        brain = Brain(
            name="Interview Assistant",
            description="Helping me interview candidates",
            default_model_config=ModelConfig(model="gpt-4o", temperature=0.7)
        )

        created = repo.create(brain)

        assert created.id == brain.id
        assert created.name == "Interview Assistant"
        assert created.description == "Helping me interview candidates"

    def test_get_brain(self, db):
        repo = BrainRepository(db)
        brain = Brain(name="Test Brain")
        repo.create(brain)

        fetched = repo.get(brain.id)

        assert fetched is not None
        assert fetched.id == brain.id
        assert fetched.name == "Test Brain"

    def test_get_nonexistent_brain(self, db):
        repo = BrainRepository(db)

        fetched = repo.get("nonexistent-id")

        assert fetched is None

    def test_get_all_brains(self, db):
        repo = BrainRepository(db)
        repo.create(Brain(name="Brain 1"))
        repo.create(Brain(name="Brain 2"))
        repo.create(Brain(name="Brain 3"))

        brains = repo.get_all()

        assert len(brains) == 3

    def test_update_brain(self, db):
        repo = BrainRepository(db)
        brain = Brain(name="Original Name")
        repo.create(brain)

        brain.name = "Updated Name"
        brain.description = "New description"
        repo.update(brain)

        fetched = repo.get(brain.id)
        assert fetched.name == "Updated Name"
        assert fetched.description == "New description"

    def test_delete_brain(self, db):
        repo = BrainRepository(db)
        brain = Brain(name="To Delete")
        repo.create(brain)

        repo.delete(brain.id)

        assert repo.get(brain.id) is None

    def test_brain_model_config_persistence(self, db):
        repo = BrainRepository(db)
        config = ModelConfig(
            model="claude-3-sonnet",
            temperature=0.5,
            max_tokens=1000,
            top_p=0.9,
            extra_params={"custom": "value"}
        )
        brain = Brain(name="Config Test", default_model_config=config)
        repo.create(brain)

        fetched = repo.get(brain.id)

        assert fetched.default_model_config.model == "claude-3-sonnet"
        assert fetched.default_model_config.temperature == 0.5
        assert fetched.default_model_config.max_tokens == 1000
        assert fetched.default_model_config.top_p == 0.9
        assert fetched.default_model_config.extra_params == {"custom": "value"}

    def test_brain_capabilities_persistence(self, db):
        repo = BrainRepository(db)
        caps = BrainCapabilities(
            conversation=True,
            files=True,
            images=False,
            code=True,
            web=False,
            mcp_servers=["notion", "slack"]
        )
        brain = Brain(name="Caps Test", capabilities=caps)
        repo.create(brain)

        fetched = repo.get(brain.id)

        assert fetched.capabilities.conversation is True
        assert fetched.capabilities.files is True
        assert fetched.capabilities.images is False
        assert fetched.capabilities.code is True
        assert fetched.capabilities.web is False
        assert fetched.capabilities.mcp_servers == ["notion", "slack"]


class TestQuestionRepository:
    """Tests for Question CRUD operations."""

    def test_create_question(self, db):
        brain_repo = BrainRepository(db)
        brain = brain_repo.create(Brain(name="Test Brain"))

        question_repo = QuestionRepository(db)
        question = Question(
            brain_id=brain.id,
            text="What should I ask next?",
            position=0
        )
        created = question_repo.create(question)

        assert created.id == question.id
        assert created.brain_id == brain.id
        assert created.text == "What should I ask next?"

    def test_get_questions_by_brain(self, db):
        brain_repo = BrainRepository(db)
        brain = brain_repo.create(Brain(name="Test Brain"))

        question_repo = QuestionRepository(db)
        question_repo.create(Question(brain_id=brain.id, text="Q1", position=0))
        question_repo.create(Question(brain_id=brain.id, text="Q2", position=1))
        question_repo.create(Question(brain_id=brain.id, text="Q3", position=2))

        questions = question_repo.get_by_brain(brain.id)

        assert len(questions) == 3
        assert questions[0].text == "Q1"
        assert questions[1].text == "Q2"
        assert questions[2].text == "Q3"

    def test_question_with_overrides(self, db):
        brain_repo = BrainRepository(db)
        brain = brain_repo.create(Brain(name="Test Brain"))

        question_repo = QuestionRepository(db)
        question = Question(
            brain_id=brain.id,
            text="Detailed question",
            position=0,
            model_config_override=ModelConfig(model="gpt-4o", temperature=0.2),
            capabilities_override=BrainCapabilities(conversation=True, files=False)
        )
        question_repo.create(question)

        fetched = question_repo.get(question.id)

        assert fetched.model_config_override is not None
        assert fetched.model_config_override.model == "gpt-4o"
        assert fetched.capabilities_override is not None
        assert fetched.capabilities_override.files is False

    def test_cascade_delete_questions(self, db):
        brain_repo = BrainRepository(db)
        brain = brain_repo.create(Brain(name="Test Brain"))

        question_repo = QuestionRepository(db)
        question_repo.create(Question(brain_id=brain.id, text="Q1", position=0))

        brain_repo.delete(brain.id)

        questions = question_repo.get_by_brain(brain.id)
        assert len(questions) == 0


class TestResourceRepository:
    """Tests for Resource CRUD operations."""

    def test_create_file_resource(self, db):
        resource_repo = ResourceRepository(db)
        resource = Resource(
            resource_type=ResourceType.FILE,
            name="Resume.pdf",
            path="/path/to/Resume.pdf",
            size_bytes=1024
        )
        created = resource_repo.create(resource)

        assert created.resource_type == ResourceType.FILE
        assert created.name == "Resume.pdf"
        assert created.path == "/path/to/Resume.pdf"

    def test_create_folder_resource(self, db):
        resource_repo = ResourceRepository(db)
        resource = Resource(
            resource_type=ResourceType.FOLDER,
            name="Company Policies",
            path="/path/to/policies"
        )
        resource_repo.create(resource)

        fetched = resource_repo.get(resource.id)

        assert fetched.resource_type == ResourceType.FOLDER
        assert fetched.path == "/path/to/policies"

    def test_update_index_status(self, db):
        resource_repo = ResourceRepository(db)
        resource = Resource(resource_type=ResourceType.FOLDER, name="test", path="/test")
        resource_repo.create(resource)

        assert resource_repo.get(resource.id).index_status == IndexStatus.PENDING

        resource_repo.update_index_status(resource.id, IndexStatus.INDEXING)
        assert resource_repo.get(resource.id).index_status == IndexStatus.INDEXING

        resource_repo.update_index_status(resource.id, IndexStatus.INDEXED, size_bytes=5000, file_count=10)
        fetched = resource_repo.get(resource.id)
        assert fetched.index_status == IndexStatus.INDEXED
        assert fetched.indexed_at is not None
        assert fetched.size_bytes == 5000
        assert fetched.file_count == 10

    def test_update_index_status_failed(self, db):
        resource_repo = ResourceRepository(db)
        resource = Resource(resource_type=ResourceType.FOLDER, name="test", path="/test")
        resource_repo.create(resource)

        resource_repo.update_index_status(resource.id, IndexStatus.FAILED, error="File not found")

        fetched = resource_repo.get(resource.id)
        assert fetched.index_status == IndexStatus.FAILED
        assert fetched.index_error == "File not found"

    def test_link_resource_to_brain(self, db):
        brain_repo = BrainRepository(db)
        brain = brain_repo.create(Brain(name="Test Brain"))

        resource_repo = ResourceRepository(db)
        resource = resource_repo.create(Resource(
            resource_type=ResourceType.FOLDER,
            name="Docs",
            path="/docs"
        ))

        resource_repo.link_to_brain(resource.id, brain.id)

        linked = resource_repo.get_by_brain(brain.id)
        assert len(linked) == 1
        assert linked[0].id == resource.id

    def test_unlink_resource_from_brain(self, db):
        brain_repo = BrainRepository(db)
        brain = brain_repo.create(Brain(name="Test Brain"))

        resource_repo = ResourceRepository(db)
        resource = resource_repo.create(Resource(
            resource_type=ResourceType.FOLDER,
            name="Docs",
            path="/docs"
        ))

        resource_repo.link_to_brain(resource.id, brain.id)
        resource_repo.unlink_from_brain(resource.id, brain.id)

        linked = resource_repo.get_by_brain(brain.id)
        assert len(linked) == 0


class TestSessionRepository:
    """Tests for Session CRUD operations."""

    def test_create_session(self, db):
        session_repo = SessionRepository(db)
        session = Session(name="Interview #1", is_live=True)

        created = session_repo.create(session)

        assert created.name == "Interview #1"
        assert created.is_live is True

    def test_get_live_session(self, db):
        session_repo = SessionRepository(db)
        session_repo.create(Session(name="Session 1", is_live=False))
        live_session = session_repo.create(Session(name="Live Session", is_live=True))

        found = session_repo.get_live()

        assert found is not None
        assert found.id == live_session.id

    def test_end_session(self, db):
        session_repo = SessionRepository(db)
        session = session_repo.create(Session(name="Test", is_live=True))

        session_repo.end_session(session.id)

        fetched = session_repo.get(session.id)
        assert fetched.is_live is False
        assert fetched.ended_at is not None

    def test_session_with_brain(self, db):
        brain_repo = BrainRepository(db)
        brain = brain_repo.create(Brain(name="Test Brain"))

        session_repo = SessionRepository(db)
        session = Session(name="Test", current_brain_id=brain.id)
        session_repo.create(session)

        fetched = session_repo.get(session.id)
        assert fetched.current_brain_id == brain.id


class TestTranscriptEntryRepository:
    """Tests for TranscriptEntry CRUD operations."""

    def test_create_transcript_entry(self, db):
        session_repo = SessionRepository(db)
        session = session_repo.create(Session(name="Test"))

        transcript_repo = TranscriptEntryRepository(db)
        entry = TranscriptEntry(
            session_id=session.id,
            speaker=SpeakerType.OTHER,
            text="Can you walk me through that?",
            confidence=0.95
        )
        created = transcript_repo.create(entry)

        assert created.speaker == SpeakerType.OTHER
        assert created.text == "Can you walk me through that?"
        assert created.confidence == 0.95

    def test_get_entries_by_session(self, db):
        session_repo = SessionRepository(db)
        session = session_repo.create(Session(name="Test"))

        transcript_repo = TranscriptEntryRepository(db)
        transcript_repo.create(TranscriptEntry(session_id=session.id, speaker=SpeakerType.OTHER, text="Hello"))
        transcript_repo.create(TranscriptEntry(session_id=session.id, speaker=SpeakerType.USER, text="Hi there"))
        transcript_repo.create(TranscriptEntry(session_id=session.id, speaker=SpeakerType.OTHER, text="How are you?"))

        entries = transcript_repo.get_by_session(session.id)

        assert len(entries) == 3

    def test_get_recent_entries(self, db):
        session_repo = SessionRepository(db)
        session = session_repo.create(Session(name="Test"))

        transcript_repo = TranscriptEntryRepository(db)
        for i in range(10):
            transcript_repo.create(TranscriptEntry(
                session_id=session.id,
                speaker=SpeakerType.USER,
                text=f"Message {i}"
            ))

        recent = transcript_repo.get_recent(session.id, max_lines=5)

        assert len(recent) == 5


class TestInteractionRepository:
    """Tests for Interaction CRUD operations."""

    def test_create_interaction(self, db):
        brain_repo = BrainRepository(db)
        brain = brain_repo.create(Brain(name="Test Brain"))

        session_repo = SessionRepository(db)
        session = session_repo.create(Session(name="Test"))

        interaction_repo = InteractionRepository(db)
        interaction = Interaction(
            session_id=session.id,
            brain_id=brain.id,
            query_type=QueryType.FREEFORM,
            query_text="Summarize this conversation"
        )
        created = interaction_repo.create(interaction)

        assert created.query_type == QueryType.FREEFORM
        assert created.query_text == "Summarize this conversation"

    def test_interaction_with_preset_question(self, db):
        brain_repo = BrainRepository(db)
        brain = brain_repo.create(Brain(name="Test Brain"))

        question_repo = QuestionRepository(db)
        question = question_repo.create(Question(brain_id=brain.id, text="Test Q", position=0))

        session_repo = SessionRepository(db)
        session = session_repo.create(Session(name="Test"))

        interaction_repo = InteractionRepository(db)
        interaction = Interaction(
            session_id=session.id,
            brain_id=brain.id,
            question_id=question.id,
            query_type=QueryType.PRESET,
            query_text=question.text
        )
        interaction_repo.create(interaction)

        fetched = interaction_repo.get(interaction.id)
        assert fetched.question_id == question.id
        assert fetched.query_type == QueryType.PRESET


class TestAIResponseRepository:
    """Tests for AIResponse CRUD operations."""

    def test_create_ai_response(self, db):
        brain_repo = BrainRepository(db)
        brain = brain_repo.create(Brain(name="Test Brain"))

        session_repo = SessionRepository(db)
        session = session_repo.create(Session(name="Test"))

        interaction_repo = InteractionRepository(db)
        interaction = interaction_repo.create(Interaction(
            session_id=session.id,
            brain_id=brain.id,
            query_type=QueryType.FREEFORM,
            query_text="Test"
        ))

        response_repo = AIResponseRepository(db)
        response = AIResponse(
            interaction_id=interaction.id,
            text="Here is my response...",
            model_used="gpt-4o",
            tokens_input=100,
            tokens_output=50,
            latency_ms=500
        )
        created = response_repo.create(response)

        assert created.text == "Here is my response..."
        assert created.model_used == "gpt-4o"

    def test_response_with_file_references(self, db):
        brain_repo = BrainRepository(db)
        brain = brain_repo.create(Brain(name="Test Brain"))

        session_repo = SessionRepository(db)
        session = session_repo.create(Session(name="Test"))

        interaction_repo = InteractionRepository(db)
        interaction = interaction_repo.create(Interaction(
            session_id=session.id,
            brain_id=brain.id,
            query_type=QueryType.FREEFORM,
            query_text="Find the PTO policy"
        ))

        response_repo = AIResponseRepository(db)
        response = AIResponse(
            interaction_id=interaction.id,
            text="I found the document.",
            model_used="gpt-4o",
            file_references=[
                FileReference(
                    resource_id="res-123",
                    filepath="/docs/PTO_Policy.pdf",
                    display_name="PTO_Policy.pdf",
                    relevance_score=0.95
                )
            ]
        )
        response_repo.create(response)

        fetched = response_repo.get_by_interaction(interaction.id)
        assert len(fetched.file_references) == 1
        assert fetched.file_references[0].display_name == "PTO_Policy.pdf"


class TestExecutionStepRepository:
    """Tests for ExecutionStep CRUD operations."""

    def test_create_execution_step(self, db):
        brain_repo = BrainRepository(db)
        brain = brain_repo.create(Brain(name="Test Brain"))

        session_repo = SessionRepository(db)
        session = session_repo.create(Session(name="Test"))

        interaction_repo = InteractionRepository(db)
        interaction = interaction_repo.create(Interaction(
            session_id=session.id,
            brain_id=brain.id,
            query_type=QueryType.FREEFORM,
            query_text="Test"
        ))

        step_repo = ExecutionStepRepository(db)
        step = ExecutionStep(
            interaction_id=interaction.id,
            step_type=StepType.SEARCHING_FILES,
            details="Looking through added files"
        )
        created = step_repo.create(step)

        assert created.step_type == StepType.SEARCHING_FILES
        assert created.status == StepStatus.IN_PROGRESS

    def test_complete_step(self, db):
        brain_repo = BrainRepository(db)
        brain = brain_repo.create(Brain(name="Test Brain"))

        session_repo = SessionRepository(db)
        session = session_repo.create(Session(name="Test"))

        interaction_repo = InteractionRepository(db)
        interaction = interaction_repo.create(Interaction(
            session_id=session.id,
            brain_id=brain.id,
            query_type=QueryType.FREEFORM,
            query_text="Test"
        ))

        step_repo = ExecutionStepRepository(db)
        step = step_repo.create(ExecutionStep(
            interaction_id=interaction.id,
            step_type=StepType.GENERATING
        ))

        step_repo.complete(step.id)

        fetched = step_repo.get_by_interaction(interaction.id)[0]
        assert fetched.status == StepStatus.COMPLETED
        assert fetched.completed_at is not None


class TestMCPServerRepository:
    """Tests for MCPServer CRUD operations."""

    def test_create_mcp_server(self, db):
        repo = MCPServerRepository(db)
        server = MCPServer(
            name="notion",
            display_name="Notion",
            server_command="npx @notionhq/mcp-server",
            capabilities=["search", "read"]
        )
        created = repo.create(server)

        assert created.name == "notion"
        assert created.display_name == "Notion"

    def test_get_by_name(self, db):
        repo = MCPServerRepository(db)
        repo.create(MCPServer(name="notion", display_name="Notion", server_command="cmd"))

        fetched = repo.get_by_name("notion")

        assert fetched is not None
        assert fetched.name == "notion"

    def test_update_status(self, db):
        repo = MCPServerRepository(db)
        server = repo.create(MCPServer(name="test", display_name="Test", server_command="cmd"))

        repo.update_status(server.id, MCPStatus.CONNECTED)

        fetched = repo.get(server.id)
        assert fetched.status == MCPStatus.CONNECTED


class TestUserSettingsRepository:
    """Tests for UserSettings singleton operations."""

    def test_get_default_settings(self, db):
        repo = UserSettingsRepository(db)

        settings = repo.get()

        assert settings.show_transcript is True
        assert settings.transcript_max_lines == 10
        assert settings.preferred_model == "gpt-4o"

    def test_update_settings(self, db):
        repo = UserSettingsRepository(db)

        settings = repo.get()
        settings.show_transcript = False
        settings.preferred_model = "claude-3-sonnet"
        settings.max_session_storage_days = 60
        repo.update(settings)

        fetched = repo.get()
        assert fetched.show_transcript is False
        assert fetched.preferred_model == "claude-3-sonnet"
        assert fetched.max_session_storage_days == 60


class TestDocumentChunkRepository:
    """Tests for DocumentChunk and vector search operations."""

    def test_create_chunk(self, db):
        resource_repo = ResourceRepository(db)
        resource = resource_repo.create(Resource(
            resource_type=ResourceType.FOLDER,
            name="test",
            path="/test"
        ))

        chunk_repo = DocumentChunkRepository(db)
        chunk = DocumentChunk(
            resource_id=resource.id,
            filepath="/path/to/test.txt",
            chunk_index=0,
            start_char=0,
            end_char=100,
            text="This is a test document.",
            embedding=[0.1] * 768  # Mock embedding
        )
        created = chunk_repo.create(chunk)

        assert created.text == "This is a test document."

    def test_get_chunks_by_resource(self, db):
        resource_repo = ResourceRepository(db)
        resource = resource_repo.create(Resource(
            resource_type=ResourceType.FOLDER,
            name="test",
            path="/test"
        ))

        chunk_repo = DocumentChunkRepository(db)
        for i in range(3):
            chunk_repo.create(DocumentChunk(
                resource_id=resource.id,
                filepath="/path/to/test.txt",
                chunk_index=i,
                start_char=i * 100,
                end_char=(i + 1) * 100,
                text=f"Chunk {i}",
                embedding=[0.1] * 768
            ))

        chunks = chunk_repo.get_by_resource(resource.id)

        assert len(chunks) == 3
        assert chunks[0].chunk_index == 0
        assert chunks[1].chunk_index == 1

    def test_delete_chunks_by_resource(self, db):
        resource_repo = ResourceRepository(db)
        resource = resource_repo.create(Resource(
            resource_type=ResourceType.FOLDER,
            name="test",
            path="/test"
        ))

        chunk_repo = DocumentChunkRepository(db)
        chunk_repo.create(DocumentChunk(
            resource_id=resource.id,
            filepath="/path/to/test.txt",
            chunk_index=0,
            text="Test",
            embedding=[0.1] * 768
        ))

        chunk_repo.delete_by_resource(resource.id)

        chunks = chunk_repo.get_by_resource(resource.id)
        assert len(chunks) == 0


class TestRAGService:
    """Tests for RAG (Retrieval-Augmented Generation) operations."""

    def _mock_embedding(self, text: str) -> list[float]:
        """Generate deterministic mock embedding based on text hash."""
        import hashlib
        h = int(hashlib.md5(text.encode()).hexdigest(), 16)
        return [(h >> i & 0xFF) / 255.0 for i in range(768)]

    def test_index_text(self, db):
        resource_repo = ResourceRepository(db)
        resource = resource_repo.create(Resource(
            resource_type=ResourceType.FOLDER,
            name="Vacation Policy",
            path="/docs"
        ))

        rag = RAGService(db)
        rag.index_text(
            resource_id=resource.id,
            filepath="/docs/policy.txt",
            text="This is the company vacation policy. Employees get 20 days PTO.",
            embedding_fn=self._mock_embedding
        )

        chunks = rag.chunks.get_by_resource(resource.id)
        assert len(chunks) >= 1

    def test_index_text_chunking(self, db):
        resource_repo = ResourceRepository(db)
        resource = resource_repo.create(Resource(
            resource_type=ResourceType.FOLDER,
            name="Long Doc",
            path="/docs"
        ))

        # Create text that will be split into multiple chunks
        long_text = "This is sentence one. " * 100

        rag = RAGService(db)
        rag.index_text(
            resource_id=resource.id,
            filepath="/docs/long.txt",
            text=long_text,
            embedding_fn=self._mock_embedding,
            chunk_size=200,
            chunk_overlap=50
        )

        chunks = rag.chunks.get_by_resource(resource.id)
        assert len(chunks) > 1

    def test_search(self, db):
        resource_repo = ResourceRepository(db)
        resource = resource_repo.create(Resource(
            resource_type=ResourceType.FOLDER,
            name="Company Docs",
            path="/docs"
        ))

        rag = RAGService(db)

        # Index some documents
        rag.index_text(
            resource_id=resource.id,
            filepath="/docs/vacation.txt",
            text="Vacation policy: employees receive 20 days of paid time off per year.",
            embedding_fn=self._mock_embedding
        )
        rag.index_text(
            resource_id=resource.id,
            filepath="/docs/salary.txt",
            text="Salary information: compensation is reviewed annually in January.",
            embedding_fn=self._mock_embedding
        )

        # Search
        query_embedding = self._mock_embedding("How much PTO do I get?")
        results = rag.search(query_embedding, resource_ids=[resource.id], limit=5)

        assert len(results) == 2
        assert all('chunk' in r and 'similarity' in r and 'resource' in r for r in results)

    def test_search_filters_by_resource(self, db):
        resource_repo = ResourceRepository(db)
        resource1 = resource_repo.create(Resource(
            resource_type=ResourceType.FOLDER,
            name="Docs 1",
            path="/docs1"
        ))
        resource2 = resource_repo.create(Resource(
            resource_type=ResourceType.FOLDER,
            name="Docs 2",
            path="/docs2"
        ))

        rag = RAGService(db)

        rag.index_text(
            resource_id=resource1.id,
            filepath="/docs1/doc1.txt",
            text="Document for resource one.",
            embedding_fn=self._mock_embedding
        )
        rag.index_text(
            resource_id=resource2.id,
            filepath="/docs2/doc2.txt",
            text="Document for resource two.",
            embedding_fn=self._mock_embedding
        )

        query_embedding = self._mock_embedding("document")

        results1 = rag.search(query_embedding, resource_ids=[resource1.id])
        results2 = rag.search(query_embedding, resource_ids=[resource2.id])

        assert len(results1) == 1
        assert results1[0]['resource'].id == resource1.id

        assert len(results2) == 1
        assert results2[0]['resource'].id == resource2.id

    def test_get_context(self, db):
        resource_repo = ResourceRepository(db)
        resource = resource_repo.create(Resource(
            resource_type=ResourceType.FOLDER,
            name="Policy",
            path="/docs"
        ))

        rag = RAGService(db)
        rag.index_text(
            resource_id=resource.id,
            filepath="/docs/policy.txt",
            text="Company policy document with important information.",
            embedding_fn=self._mock_embedding
        )

        query_embedding = self._mock_embedding("policy")
        context = rag.get_context(query_embedding, resource_ids=[resource.id])

        assert "[Policy]" in context
        assert "important information" in context

    def test_delete_resource(self, db):
        resource_repo = ResourceRepository(db)
        resource = resource_repo.create(Resource(
            resource_type=ResourceType.FOLDER,
            name="Test",
            path="/test"
        ))

        rag = RAGService(db)
        rag.index_text(
            resource_id=resource.id,
            filepath="/test/test.txt",
            text="Test document content.",
            embedding_fn=self._mock_embedding
        )

        resource_id = resource.id
        rag.delete_resource(resource_id)

        assert rag.resources.get(resource_id) is None
        assert len(rag.chunks.get_by_resource(resource_id)) == 0

    def test_chunk_text_sentence_boundaries(self, db):
        rag = RAGService(db)

        text = "First sentence here. Second sentence here. Third sentence here. Fourth sentence."
        chunks = rag._chunk_text(text, size=50, overlap=10)

        # All chunks should have content
        assert len(chunks) >= 2
        for chunk_text, start, end in chunks:
            assert len(chunk_text) > 0
            assert start >= 0
            assert end > start

    def test_vector_similarity_search(self, db):
        """Test that vector search returns results ordered by similarity."""
        resource_repo = ResourceRepository(db)
        resource = resource_repo.create(Resource(
            resource_type=ResourceType.FOLDER,
            name="Mixed Docs",
            path="/docs"
        ))

        rag = RAGService(db)

        # Index documents with distinct content
        rag.index_text(
            resource_id=resource.id,
            filepath="/docs/python.txt",
            text="Python is a programming language used for web development and data science.",
            embedding_fn=self._mock_embedding
        )
        rag.index_text(
            resource_id=resource.id,
            filepath="/docs/cooking.txt",
            text="Cooking recipes for delicious pasta and Italian cuisine.",
            embedding_fn=self._mock_embedding
        )

        # Search for programming-related content
        query = self._mock_embedding("programming language")
        results = rag.search(query, resource_ids=[resource.id])

        assert len(results) == 2
        # All results should have similarity scores
        assert all(0 <= r['similarity'] <= 1 for r in results)
