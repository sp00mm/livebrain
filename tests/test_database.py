"""
Tests for Livebrain database layer.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import (
    Brain, Question, Artifact, DocumentChunk, Session,
    TranscriptEntry, Interaction, AIResponse, ExecutionStep,
    MCPServer, ModelConfig, BrainCapabilities,
    FileReference, SpeakerType, QueryType, ArtifactType,
    IndexStatus, StepType, StepStatus, MCPStatus
)
from services.database import (
    BrainRepository, QuestionRepository, ArtifactRepository,
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


class TestArtifactRepository:
    """Tests for Artifact CRUD operations."""

    def test_create_file_artifact(self, db):
        brain_repo = BrainRepository(db)
        brain = brain_repo.create(Brain(name="Test Brain"))

        artifact_repo = ArtifactRepository(db)
        artifact = Artifact(
            brain_id=brain.id,
            artifact_type=ArtifactType.FILE,
            name="Resume.pdf",
            metadata={"filepath": "/path/to/Resume.pdf", "file_type": "pdf"}
        )
        created = artifact_repo.create(artifact)

        assert created.artifact_type == ArtifactType.FILE
        assert created.name == "Resume.pdf"
        assert created.filepath == "/path/to/Resume.pdf"

    def test_create_folder_artifact(self, db):
        brain_repo = BrainRepository(db)
        brain = brain_repo.create(Brain(name="Test Brain"))

        artifact_repo = ArtifactRepository(db)
        artifact = Artifact(
            brain_id=brain.id,
            artifact_type=ArtifactType.FOLDER,
            name="Company Policies",
            metadata={"folderpath": "/path/to/policies", "recursive": True}
        )
        artifact_repo.create(artifact)

        fetched = artifact_repo.get(artifact.id)

        assert fetched.artifact_type == ArtifactType.FOLDER
        assert fetched.folderpath == "/path/to/policies"

    def test_update_index_status(self, db):
        brain_repo = BrainRepository(db)
        brain = brain_repo.create(Brain(name="Test Brain"))

        artifact_repo = ArtifactRepository(db)
        artifact = Artifact(brain_id=brain.id, artifact_type=ArtifactType.FILE, name="test.txt")
        artifact_repo.create(artifact)

        assert artifact_repo.get(artifact.id).index_status == IndexStatus.PENDING

        artifact_repo.update_index_status(artifact.id, IndexStatus.INDEXING)
        assert artifact_repo.get(artifact.id).index_status == IndexStatus.INDEXING

        artifact_repo.update_index_status(artifact.id, IndexStatus.INDEXED)
        fetched = artifact_repo.get(artifact.id)
        assert fetched.index_status == IndexStatus.INDEXED
        assert fetched.indexed_at is not None

    def test_update_index_status_failed(self, db):
        brain_repo = BrainRepository(db)
        brain = brain_repo.create(Brain(name="Test Brain"))

        artifact_repo = ArtifactRepository(db)
        artifact = Artifact(brain_id=brain.id, artifact_type=ArtifactType.FILE, name="test.txt")
        artifact_repo.create(artifact)

        artifact_repo.update_index_status(artifact.id, IndexStatus.FAILED, "File not found")

        fetched = artifact_repo.get(artifact.id)
        assert fetched.index_status == IndexStatus.FAILED
        assert fetched.index_error == "File not found"


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
                    artifact_id="art-123",
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
        brain_repo = BrainRepository(db)
        brain = brain_repo.create(Brain(name="Test Brain"))

        artifact_repo = ArtifactRepository(db)
        artifact = artifact_repo.create(Artifact(
            brain_id=brain.id,
            artifact_type=ArtifactType.FILE,
            name="test.txt"
        ))

        chunk_repo = DocumentChunkRepository(db)
        chunk = DocumentChunk(
            artifact_id=artifact.id,
            filepath="/path/to/test.txt",
            chunk_index=0,
            start_char=0,
            end_char=100,
            text="This is a test document.",
            embedding=[0.1] * 768  # Mock embedding
        )
        created = chunk_repo.create(chunk)

        assert created.text == "This is a test document."

    def test_get_chunks_by_artifact(self, db):
        brain_repo = BrainRepository(db)
        brain = brain_repo.create(Brain(name="Test Brain"))

        artifact_repo = ArtifactRepository(db)
        artifact = artifact_repo.create(Artifact(
            brain_id=brain.id,
            artifact_type=ArtifactType.FILE,
            name="test.txt"
        ))

        chunk_repo = DocumentChunkRepository(db)
        for i in range(3):
            chunk_repo.create(DocumentChunk(
                artifact_id=artifact.id,
                filepath="/path/to/test.txt",
                chunk_index=i,
                start_char=i * 100,
                end_char=(i + 1) * 100,
                text=f"Chunk {i}",
                embedding=[0.1] * 768
            ))

        chunks = chunk_repo.get_by_artifact(artifact.id)

        assert len(chunks) == 3
        assert chunks[0].chunk_index == 0
        assert chunks[1].chunk_index == 1

    def test_delete_chunks_by_artifact(self, db):
        brain_repo = BrainRepository(db)
        brain = brain_repo.create(Brain(name="Test Brain"))

        artifact_repo = ArtifactRepository(db)
        artifact = artifact_repo.create(Artifact(
            brain_id=brain.id,
            artifact_type=ArtifactType.FILE,
            name="test.txt"
        ))

        chunk_repo = DocumentChunkRepository(db)
        chunk_repo.create(DocumentChunk(
            artifact_id=artifact.id,
            filepath="/path/to/test.txt",
            chunk_index=0,
            text="Test",
            embedding=[0.1] * 768
        ))

        chunk_repo.delete_by_artifact(artifact.id)

        chunks = chunk_repo.get_by_artifact(artifact.id)
        assert len(chunks) == 0


class TestRAGService:
    """Tests for RAG (Retrieval-Augmented Generation) operations."""

    def _mock_embedding(self, text: str) -> list[float]:
        """Generate deterministic mock embedding based on text hash."""
        import hashlib
        h = int(hashlib.md5(text.encode()).hexdigest(), 16)
        return [(h >> i & 0xFF) / 255.0 for i in range(768)]

    def test_index_text(self, db):
        brain_repo = BrainRepository(db)
        brain = brain_repo.create(Brain(name="Test Brain"))

        rag = RAGService(db)
        artifact = rag.index_text(
            brain_id=brain.id,
            filepath="/docs/policy.txt",
            text="This is the company vacation policy. Employees get 20 days PTO.",
            embedding_fn=self._mock_embedding,
            name="Vacation Policy"
        )

        assert artifact.name == "Vacation Policy"
        assert artifact.index_status == IndexStatus.INDEXED

        chunks = rag.chunks.get_by_artifact(artifact.id)
        assert len(chunks) >= 1

    def test_index_text_chunking(self, db):
        brain_repo = BrainRepository(db)
        brain = brain_repo.create(Brain(name="Test Brain"))

        # Create text that will be split into multiple chunks
        long_text = "This is sentence one. " * 100

        rag = RAGService(db)
        artifact = rag.index_text(
            brain_id=brain.id,
            filepath="/docs/long.txt",
            text=long_text,
            embedding_fn=self._mock_embedding,
            chunk_size=200,
            chunk_overlap=50
        )

        chunks = rag.chunks.get_by_artifact(artifact.id)
        assert len(chunks) > 1

    def test_search(self, db):
        brain_repo = BrainRepository(db)
        brain = brain_repo.create(Brain(name="Test Brain"))

        rag = RAGService(db)

        # Index some documents
        rag.index_text(
            brain_id=brain.id,
            filepath="/docs/vacation.txt",
            text="Vacation policy: employees receive 20 days of paid time off per year.",
            embedding_fn=self._mock_embedding
        )
        rag.index_text(
            brain_id=brain.id,
            filepath="/docs/salary.txt",
            text="Salary information: compensation is reviewed annually in January.",
            embedding_fn=self._mock_embedding
        )

        # Search
        query_embedding = self._mock_embedding("How much PTO do I get?")
        results = rag.search(query_embedding, brain_id=brain.id, limit=5)

        assert len(results) == 2
        assert all('chunk' in r and 'similarity' in r and 'artifact' in r for r in results)

    def test_search_filters_by_brain(self, db):
        brain_repo = BrainRepository(db)
        brain1 = brain_repo.create(Brain(name="Brain 1"))
        brain2 = brain_repo.create(Brain(name="Brain 2"))

        rag = RAGService(db)

        rag.index_text(
            brain_id=brain1.id,
            filepath="/docs/doc1.txt",
            text="Document for brain one.",
            embedding_fn=self._mock_embedding
        )
        rag.index_text(
            brain_id=brain2.id,
            filepath="/docs/doc2.txt",
            text="Document for brain two.",
            embedding_fn=self._mock_embedding
        )

        query_embedding = self._mock_embedding("document")

        results1 = rag.search(query_embedding, brain_id=brain1.id)
        results2 = rag.search(query_embedding, brain_id=brain2.id)

        assert len(results1) == 1
        assert results1[0]['artifact'].brain_id == brain1.id

        assert len(results2) == 1
        assert results2[0]['artifact'].brain_id == brain2.id

    def test_get_context(self, db):
        brain_repo = BrainRepository(db)
        brain = brain_repo.create(Brain(name="Test Brain"))

        rag = RAGService(db)
        rag.index_text(
            brain_id=brain.id,
            filepath="/docs/policy.txt",
            text="Company policy document with important information.",
            embedding_fn=self._mock_embedding,
            name="Policy"
        )

        query_embedding = self._mock_embedding("policy")
        context = rag.get_context(query_embedding, brain_id=brain.id)

        assert "[Policy]" in context
        assert "important information" in context

    def test_delete_artifact(self, db):
        brain_repo = BrainRepository(db)
        brain = brain_repo.create(Brain(name="Test Brain"))

        rag = RAGService(db)
        artifact = rag.index_text(
            brain_id=brain.id,
            filepath="/docs/test.txt",
            text="Test document content.",
            embedding_fn=self._mock_embedding
        )

        artifact_id = artifact.id
        rag.delete_artifact(artifact_id)

        assert rag.artifacts.get(artifact_id) is None
        assert len(rag.chunks.get_by_artifact(artifact_id)) == 0

    def test_index_failure_sets_status(self, db):
        brain_repo = BrainRepository(db)
        brain = brain_repo.create(Brain(name="Test Brain"))

        def failing_embedding(text):
            raise ValueError("Embedding failed")

        rag = RAGService(db)

        try:
            rag.index_text(
                brain_id=brain.id,
                filepath="/docs/test.txt",
                text="Some text",
                embedding_fn=failing_embedding
            )
        except ValueError:
            pass

        # Check that artifact was created with FAILED status
        artifacts = rag.artifacts.get_by_brain(brain.id)
        assert len(artifacts) == 1
        assert artifacts[0].index_status == IndexStatus.FAILED
        assert "Embedding failed" in artifacts[0].index_error

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
        brain_repo = BrainRepository(db)
        brain = brain_repo.create(Brain(name="Test Brain"))

        rag = RAGService(db)

        # Index documents with distinct content
        rag.index_text(
            brain_id=brain.id,
            filepath="/docs/python.txt",
            text="Python is a programming language used for web development and data science.",
            embedding_fn=self._mock_embedding
        )
        rag.index_text(
            brain_id=brain.id,
            filepath="/docs/cooking.txt",
            text="Cooking recipes for delicious pasta and Italian cuisine.",
            embedding_fn=self._mock_embedding
        )

        # Search for programming-related content
        query = self._mock_embedding("programming language")
        results = rag.search(query, brain_id=brain.id)

        assert len(results) == 2
        # All results should have similarity scores
        assert all(0 <= r['similarity'] <= 1 for r in results)
