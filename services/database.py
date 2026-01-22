"""
Livebrain Database Service

Handles database initialization, schema management, and provides
repository classes for each entity.
"""

import json
import os
import sys
from datetime import datetime, timezone
from typing import Optional

import libsql

from models import (
    Brain, Question, Artifact, DocumentChunk, Session,
    TranscriptEntry, Interaction, AIResponse, ExecutionStep,
    MCPServer, UserSettings, ModelConfig, BrainCapabilities,
    FileReference, SpeakerType, QueryType, ArtifactType,
    IndexStatus, StepType, StepStatus, MCPStatus
)


# =============================================================================
# Database Connection
# =============================================================================

class Database:
    """Main database connection and schema management."""

    EMBEDDING_DIMENSION = 768  # Default for embeddinggemma

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            db_path = self.get_default_db_path()
        self.db_path = db_path
        self.conn = libsql.connect(f"file:{db_path}")

    @staticmethod
    def get_default_db_path() -> str:
        """Get the default database path for the platform."""
        if sys.platform == 'darwin':
            app_support = os.path.expanduser("~/Library/Application Support/LiveBrain")
        else:
            app_support = os.path.expanduser("~/.livebrain")
        os.makedirs(app_support, exist_ok=True)
        return os.path.join(app_support, "livebrain.db")

    def initialize_schema(self):
        """Initialize database schema from schema.sql."""
        schema_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'db', 'schema.sql')
        with open(schema_file, 'r') as f:
            sql = f.read()
        for statement in sql.split(';'):
            statement = statement.strip()
            if statement:
                self.conn.execute(statement)
        self.conn.commit()


# =============================================================================
# Helpers
# =============================================================================

def _dt_to_str(dt: Optional[datetime]) -> Optional[str]:
    """Convert datetime to ISO string."""
    return dt.isoformat() if dt else None

def _str_to_dt(s: Optional[str]) -> Optional[datetime]:
    """Convert ISO string to datetime."""
    return datetime.fromisoformat(s) if s else None


# =============================================================================
# Repository: Brains
# =============================================================================

class BrainRepository:
    """CRUD operations for Brain entities."""

    def __init__(self, db: Database):
        self.db = db
        self.conn = db.conn

    def create(self, brain: Brain) -> Brain:
        self.conn.execute("""
            INSERT INTO brains (id, name, description, default_model_config_json,
                              capabilities_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, [
            brain.id,
            brain.name,
            brain.description,
            json.dumps(brain.default_model_config.to_dict()),
            json.dumps(brain.capabilities.to_dict()),
            _dt_to_str(brain.created_at),
            _dt_to_str(brain.updated_at)
        ])
        self.conn.commit()
        return brain

    def get(self, brain_id: str) -> Optional[Brain]:
        cursor = self.conn.execute(
            "SELECT * FROM brains WHERE id = ?", [brain_id]
        )
        row = cursor.fetchone()
        return self._row_to_brain(row) if row else None

    def get_all(self) -> list[Brain]:
        cursor = self.conn.execute("SELECT * FROM brains ORDER BY created_at DESC")
        return [self._row_to_brain(row) for row in cursor.fetchall()]

    def update(self, brain: Brain) -> Brain:
        brain.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        self.conn.execute("""
            UPDATE brains SET name = ?, description = ?, default_model_config_json = ?,
                            capabilities_json = ?, updated_at = ?
            WHERE id = ?
        """, [
            brain.name,
            brain.description,
            json.dumps(brain.default_model_config.to_dict()),
            json.dumps(brain.capabilities.to_dict()),
            _dt_to_str(brain.updated_at),
            brain.id
        ])
        self.conn.commit()
        return brain

    def delete(self, brain_id: str) -> bool:
        self.conn.execute("DELETE FROM brains WHERE id = ?", [brain_id])
        self.conn.commit()
        return True

    def _row_to_brain(self, row) -> Brain:
        return Brain(
            id=row[0],
            name=row[1],
            description=row[2] or "",
            default_model_config=ModelConfig.from_dict(json.loads(row[3])),
            capabilities=BrainCapabilities.from_dict(json.loads(row[4])),
            created_at=_str_to_dt(row[5]),
            updated_at=_str_to_dt(row[6])
        )


# =============================================================================
# Repository: Questions
# =============================================================================

class QuestionRepository:
    """CRUD operations for Question entities."""

    def __init__(self, db: Database):
        self.db = db
        self.conn = db.conn

    def create(self, question: Question) -> Question:
        self.conn.execute("""
            INSERT INTO questions (id, brain_id, text, position,
                                 model_config_override_json, capabilities_override_json,
                                 created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            question.id,
            question.brain_id,
            question.text,
            question.position,
            json.dumps(question.model_config_override.to_dict()) if question.model_config_override else None,
            json.dumps(question.capabilities_override.to_dict()) if question.capabilities_override else None,
            _dt_to_str(question.created_at),
            _dt_to_str(question.updated_at)
        ])
        self.conn.commit()
        return question

    def get(self, question_id: str) -> Optional[Question]:
        cursor = self.conn.execute(
            "SELECT * FROM questions WHERE id = ?", [question_id]
        )
        row = cursor.fetchone()
        return self._row_to_question(row) if row else None

    def get_by_brain(self, brain_id: str) -> list[Question]:
        cursor = self.conn.execute(
            "SELECT * FROM questions WHERE brain_id = ? ORDER BY position",
            [brain_id]
        )
        return [self._row_to_question(row) for row in cursor.fetchall()]

    def update(self, question: Question) -> Question:
        question.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        self.conn.execute("""
            UPDATE questions SET text = ?, position = ?,
                               model_config_override_json = ?, capabilities_override_json = ?,
                               updated_at = ?
            WHERE id = ?
        """, [
            question.text,
            question.position,
            json.dumps(question.model_config_override.to_dict()) if question.model_config_override else None,
            json.dumps(question.capabilities_override.to_dict()) if question.capabilities_override else None,
            _dt_to_str(question.updated_at),
            question.id
        ])
        self.conn.commit()
        return question

    def delete(self, question_id: str) -> bool:
        self.conn.execute("DELETE FROM questions WHERE id = ?", [question_id])
        self.conn.commit()
        return True

    def _row_to_question(self, row) -> Question:
        return Question(
            id=row[0],
            brain_id=row[1],
            text=row[2],
            position=row[3],
            model_config_override=ModelConfig.from_dict(json.loads(row[4])) if row[4] else None,
            capabilities_override=BrainCapabilities.from_dict(json.loads(row[5])) if row[5] else None,
            created_at=_str_to_dt(row[6]),
            updated_at=_str_to_dt(row[7])
        )


# =============================================================================
# Repository: Artifacts
# =============================================================================

class ArtifactRepository:
    """CRUD operations for Artifact entities."""

    def __init__(self, db: Database):
        self.db = db
        self.conn = db.conn

    def create(self, artifact: Artifact) -> Artifact:
        self.conn.execute("""
            INSERT INTO artifacts (id, brain_id, artifact_type, name, metadata_json,
                                 index_status, indexed_at, index_error, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            artifact.id,
            artifact.brain_id,
            artifact.artifact_type.value,
            artifact.name,
            json.dumps(artifact.metadata),
            artifact.index_status.value,
            _dt_to_str(artifact.indexed_at),
            artifact.index_error,
            _dt_to_str(artifact.created_at)
        ])
        self.conn.commit()
        return artifact

    def get(self, artifact_id: str) -> Optional[Artifact]:
        cursor = self.conn.execute(
            "SELECT * FROM artifacts WHERE id = ?", [artifact_id]
        )
        row = cursor.fetchone()
        return self._row_to_artifact(row) if row else None

    def get_by_brain(self, brain_id: str) -> list[Artifact]:
        cursor = self.conn.execute(
            "SELECT * FROM artifacts WHERE brain_id = ? ORDER BY created_at DESC",
            [brain_id]
        )
        return [self._row_to_artifact(row) for row in cursor.fetchall()]

    def update_index_status(self, artifact_id: str, status: IndexStatus,
                           error: Optional[str] = None) -> None:
        indexed_at = _dt_to_str(datetime.now(timezone.utc).replace(tzinfo=None)) if status == IndexStatus.INDEXED else None
        self.conn.execute("""
            UPDATE artifacts SET index_status = ?, indexed_at = ?, index_error = ?
            WHERE id = ?
        """, [status.value, indexed_at, error, artifact_id])
        self.conn.commit()

    def delete(self, artifact_id: str) -> bool:
        self.conn.execute("DELETE FROM artifacts WHERE id = ?", [artifact_id])
        self.conn.commit()
        return True

    def _row_to_artifact(self, row) -> Artifact:
        return Artifact(
            id=row[0],
            brain_id=row[1],
            artifact_type=ArtifactType(row[2]),
            name=row[3],
            metadata=json.loads(row[4]),
            index_status=IndexStatus(row[5]),
            indexed_at=_str_to_dt(row[6]),
            index_error=row[7],
            created_at=_str_to_dt(row[8])
        )


# =============================================================================
# Repository: DocumentChunks (Vector Store)
# =============================================================================

class DocumentChunkRepository:
    """CRUD and vector search for DocumentChunk entities."""

    def __init__(self, db: Database):
        self.db = db
        self.conn = db.conn

    def create(self, chunk: DocumentChunk) -> DocumentChunk:
        embedding_json = json.dumps(chunk.embedding)
        self.conn.execute("""
            INSERT INTO document_chunks (id, artifact_id, filepath, chunk_index,
                                        start_char, end_char, text, embedding, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, vector32(?), ?)
        """, [
            chunk.id,
            chunk.artifact_id,
            chunk.filepath,
            chunk.chunk_index,
            chunk.start_char,
            chunk.end_char,
            chunk.text,
            embedding_json,
            _dt_to_str(chunk.created_at)
        ])
        self.conn.commit()
        return chunk

    def create_many(self, chunks: list[DocumentChunk]) -> None:
        """Batch insert multiple chunks."""
        for chunk in chunks:
            self.create(chunk)

    def get_by_artifact(self, artifact_id: str) -> list[DocumentChunk]:
        cursor = self.conn.execute(
            "SELECT id, artifact_id, filepath, chunk_index, start_char, end_char, text, created_at "
            "FROM document_chunks WHERE artifact_id = ? ORDER BY chunk_index",
            [artifact_id]
        )
        return [self._row_to_chunk(row) for row in cursor.fetchall()]

    def delete_by_artifact(self, artifact_id: str) -> None:
        self.conn.execute("DELETE FROM document_chunks WHERE artifact_id = ?", [artifact_id])
        self.conn.commit()

    def search(self, query_embedding: list[float], limit: int = 10,
              brain_id: Optional[str] = None) -> list[tuple[DocumentChunk, float]]:
        """
        Search for similar chunks using vector similarity.
        Returns list of (chunk, similarity_score) tuples.
        """
        embedding_json = json.dumps(query_embedding)

        if brain_id:
            # Filter by brain via artifacts
            cursor = self.conn.execute("""
                SELECT dc.id, dc.artifact_id, dc.filepath, dc.chunk_index,
                       dc.start_char, dc.end_char, dc.text, dc.created_at,
                       vector_distance_cos(dc.embedding, vector32(?)) as distance
                FROM vector_top_k('idx_chunks_embedding', vector32(?), ?) as vtk
                JOIN document_chunks dc ON dc.rowid = vtk.id
                JOIN artifacts a ON a.id = dc.artifact_id
                WHERE a.brain_id = ?
                ORDER BY distance ASC
            """, [embedding_json, embedding_json, limit * 2, brain_id])
        else:
            cursor = self.conn.execute("""
                SELECT dc.id, dc.artifact_id, dc.filepath, dc.chunk_index,
                       dc.start_char, dc.end_char, dc.text, dc.created_at,
                       vector_distance_cos(dc.embedding, vector32(?)) as distance
                FROM vector_top_k('idx_chunks_embedding', vector32(?), ?) as vtk
                JOIN document_chunks dc ON dc.rowid = vtk.id
                ORDER BY distance ASC
            """, [embedding_json, embedding_json, limit])

        results = []
        for row in cursor.fetchall()[:limit]:
            chunk = self._row_to_chunk(row[:8])
            similarity = 1 - row[8]  # Convert distance to similarity
            results.append((chunk, similarity))
        return results

    def _row_to_chunk(self, row) -> DocumentChunk:
        return DocumentChunk(
            id=row[0],
            artifact_id=row[1],
            filepath=row[2],
            chunk_index=row[3],
            start_char=row[4],
            end_char=row[5],
            text=row[6],
            embedding=[],  # Don't load embedding by default
            created_at=_str_to_dt(row[7])
        )


# =============================================================================
# Repository: Sessions
# =============================================================================

class SessionRepository:
    """CRUD operations for Session entities."""

    def __init__(self, db: Database):
        self.db = db
        self.conn = db.conn

    def create(self, session: Session) -> Session:
        self.conn.execute("""
            INSERT INTO sessions (id, name, audio_input_device, audio_output_device,
                                is_live, current_brain_id, created_at, ended_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            session.id,
            session.name,
            session.audio_input_device,
            session.audio_output_device,
            1 if session.is_live else 0,
            session.current_brain_id,
            _dt_to_str(session.created_at),
            _dt_to_str(session.ended_at)
        ])
        self.conn.commit()
        return session

    def get(self, session_id: str) -> Optional[Session]:
        cursor = self.conn.execute(
            "SELECT * FROM sessions WHERE id = ?", [session_id]
        )
        row = cursor.fetchone()
        return self._row_to_session(row) if row else None

    def get_recent(self, limit: int = 20) -> list[Session]:
        cursor = self.conn.execute(
            "SELECT * FROM sessions ORDER BY created_at DESC LIMIT ?", [limit]
        )
        return [self._row_to_session(row) for row in cursor.fetchall()]

    def get_live(self) -> Optional[Session]:
        cursor = self.conn.execute(
            "SELECT * FROM sessions WHERE is_live = 1 LIMIT 1"
        )
        row = cursor.fetchone()
        return self._row_to_session(row) if row else None

    def update(self, session: Session) -> Session:
        self.conn.execute("""
            UPDATE sessions SET name = ?, is_live = ?, current_brain_id = ?, ended_at = ?
            WHERE id = ?
        """, [
            session.name,
            1 if session.is_live else 0,
            session.current_brain_id,
            _dt_to_str(session.ended_at),
            session.id
        ])
        self.conn.commit()
        return session

    def end_session(self, session_id: str) -> None:
        self.conn.execute("""
            UPDATE sessions SET is_live = 0, ended_at = ? WHERE id = ?
        """, [_dt_to_str(datetime.now(timezone.utc).replace(tzinfo=None)), session_id])
        self.conn.commit()

    def delete(self, session_id: str) -> bool:
        self.conn.execute("DELETE FROM sessions WHERE id = ?", [session_id])
        self.conn.commit()
        return True

    def _row_to_session(self, row) -> Session:
        return Session(
            id=row[0],
            name=row[1] or "",
            audio_input_device=row[2],
            audio_output_device=row[3],
            is_live=bool(row[4]),
            current_brain_id=row[5],
            created_at=_str_to_dt(row[6]),
            ended_at=_str_to_dt(row[7])
        )


# =============================================================================
# Repository: TranscriptEntries
# =============================================================================

class TranscriptEntryRepository:
    """CRUD operations for TranscriptEntry entities."""

    def __init__(self, db: Database):
        self.db = db
        self.conn = db.conn

    def create(self, entry: TranscriptEntry) -> TranscriptEntry:
        self.conn.execute("""
            INSERT INTO transcript_entries (id, session_id, speaker, text, confidence, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
        """, [
            entry.id,
            entry.session_id,
            entry.speaker.value,
            entry.text,
            entry.confidence,
            _dt_to_str(entry.timestamp)
        ])
        self.conn.commit()
        return entry

    def get_by_session(self, session_id: str, limit: Optional[int] = None) -> list[TranscriptEntry]:
        if limit:
            cursor = self.conn.execute(
                "SELECT * FROM transcript_entries WHERE session_id = ? "
                "ORDER BY timestamp DESC LIMIT ?",
                [session_id, limit]
            )
        else:
            cursor = self.conn.execute(
                "SELECT * FROM transcript_entries WHERE session_id = ? ORDER BY timestamp",
                [session_id]
            )
        entries = [self._row_to_entry(row) for row in cursor.fetchall()]
        return list(reversed(entries)) if limit else entries

    def get_recent(self, session_id: str, max_lines: int = 10) -> list[TranscriptEntry]:
        """Get the most recent transcript entries for display."""
        return self.get_by_session(session_id, limit=max_lines)

    def _row_to_entry(self, row) -> TranscriptEntry:
        return TranscriptEntry(
            id=row[0],
            session_id=row[1],
            speaker=SpeakerType(row[2]),
            text=row[3],
            confidence=row[4] or 1.0,
            timestamp=_str_to_dt(row[5])
        )


# =============================================================================
# Repository: Interactions
# =============================================================================

class InteractionRepository:
    """CRUD operations for Interaction entities."""

    def __init__(self, db: Database):
        self.db = db
        self.conn = db.conn

    def create(self, interaction: Interaction) -> Interaction:
        self.conn.execute("""
            INSERT INTO interactions (id, session_id, brain_id, question_id,
                                     query_type, query_text, transcript_snapshot_json,
                                     artifacts_used_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            interaction.id,
            interaction.session_id,
            interaction.brain_id,
            interaction.question_id,
            interaction.query_type.value,
            interaction.query_text,
            json.dumps(interaction.transcript_snapshot),
            json.dumps(interaction.artifacts_used),
            _dt_to_str(interaction.created_at)
        ])
        self.conn.commit()
        return interaction

    def get(self, interaction_id: str) -> Optional[Interaction]:
        cursor = self.conn.execute(
            "SELECT * FROM interactions WHERE id = ?", [interaction_id]
        )
        row = cursor.fetchone()
        return self._row_to_interaction(row) if row else None

    def get_by_session(self, session_id: str) -> list[Interaction]:
        cursor = self.conn.execute(
            "SELECT * FROM interactions WHERE session_id = ? ORDER BY created_at",
            [session_id]
        )
        return [self._row_to_interaction(row) for row in cursor.fetchall()]

    def update(self, interaction: Interaction) -> Interaction:
        self.conn.execute("""
            UPDATE interactions SET
                transcript_snapshot_json = ?,
                artifacts_used_json = ?
            WHERE id = ?
        """, [
            json.dumps(interaction.transcript_snapshot),
            json.dumps(interaction.artifacts_used),
            interaction.id
        ])
        self.conn.commit()
        return interaction

    def _row_to_interaction(self, row) -> Interaction:
        return Interaction(
            id=row[0],
            session_id=row[1],
            brain_id=row[2],
            question_id=row[3],
            query_type=QueryType(row[4]),
            query_text=row[5],
            transcript_snapshot=json.loads(row[6]) if row[6] else [],
            artifacts_used=json.loads(row[7]) if row[7] else [],
            created_at=_str_to_dt(row[8])
        )


# =============================================================================
# Repository: AIResponses
# =============================================================================

class AIResponseRepository:
    """CRUD operations for AIResponse entities."""

    def __init__(self, db: Database):
        self.db = db
        self.conn = db.conn

    def create(self, response: AIResponse) -> AIResponse:
        file_refs_json = json.dumps([r.to_dict() for r in response.file_references])
        self.conn.execute("""
            INSERT INTO ai_responses (id, interaction_id, text, file_references_json,
                                     model_used, tokens_input, tokens_output,
                                     latency_ms, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            response.id,
            response.interaction_id,
            response.text,
            file_refs_json,
            response.model_used,
            response.tokens_input,
            response.tokens_output,
            response.latency_ms,
            _dt_to_str(response.created_at)
        ])
        self.conn.commit()
        return response

    def get_by_interaction(self, interaction_id: str) -> Optional[AIResponse]:
        cursor = self.conn.execute(
            "SELECT * FROM ai_responses WHERE interaction_id = ?", [interaction_id]
        )
        row = cursor.fetchone()
        return self._row_to_response(row) if row else None

    def update_text(self, response_id: str, text: str) -> None:
        """Update response text (for streaming)."""
        self.conn.execute(
            "UPDATE ai_responses SET text = ? WHERE id = ?",
            [text, response_id]
        )
        self.conn.commit()

    def _row_to_response(self, row) -> AIResponse:
        file_refs = [FileReference.from_dict(r) for r in json.loads(row[3])] if row[3] else []
        return AIResponse(
            id=row[0],
            interaction_id=row[1],
            text=row[2],
            file_references=file_refs,
            model_used=row[4],
            tokens_input=row[5] or 0,
            tokens_output=row[6] or 0,
            latency_ms=row[7] or 0,
            created_at=_str_to_dt(row[8])
        )


# =============================================================================
# Repository: ExecutionSteps
# =============================================================================

class ExecutionStepRepository:
    """CRUD operations for ExecutionStep entities."""

    def __init__(self, db: Database):
        self.db = db
        self.conn = db.conn

    def create(self, step: ExecutionStep) -> ExecutionStep:
        self.conn.execute("""
            INSERT INTO execution_steps (id, interaction_id, step_type, status,
                                        details, started_at, completed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, [
            step.id,
            step.interaction_id,
            step.step_type.value,
            step.status.value,
            step.details,
            _dt_to_str(step.started_at),
            _dt_to_str(step.completed_at)
        ])
        self.conn.commit()
        return step

    def get_by_interaction(self, interaction_id: str) -> list[ExecutionStep]:
        cursor = self.conn.execute(
            "SELECT * FROM execution_steps WHERE interaction_id = ? ORDER BY started_at",
            [interaction_id]
        )
        return [self._row_to_step(row) for row in cursor.fetchall()]

    def complete(self, step_id: str, status: StepStatus = StepStatus.COMPLETED) -> None:
        self.conn.execute("""
            UPDATE execution_steps SET status = ?, completed_at = ? WHERE id = ?
        """, [status.value, _dt_to_str(datetime.now(timezone.utc).replace(tzinfo=None)), step_id])
        self.conn.commit()

    def _row_to_step(self, row) -> ExecutionStep:
        return ExecutionStep(
            id=row[0],
            interaction_id=row[1],
            step_type=StepType(row[2]),
            status=StepStatus(row[3]),
            details=row[4],
            started_at=_str_to_dt(row[5]),
            completed_at=_str_to_dt(row[6])
        )


# =============================================================================
# Repository: MCPServers
# =============================================================================

class MCPServerRepository:
    """CRUD operations for MCPServer entities."""

    def __init__(self, db: Database):
        self.db = db
        self.conn = db.conn

    def create(self, server: MCPServer) -> MCPServer:
        self.conn.execute("""
            INSERT INTO mcp_servers (id, name, display_name, server_command,
                                    status, capabilities_json)
            VALUES (?, ?, ?, ?, ?, ?)
        """, [
            server.id,
            server.name,
            server.display_name,
            server.server_command,
            server.status.value,
            json.dumps(server.capabilities)
        ])
        self.conn.commit()
        return server

    def get(self, server_id: str) -> Optional[MCPServer]:
        cursor = self.conn.execute(
            "SELECT * FROM mcp_servers WHERE id = ?", [server_id]
        )
        row = cursor.fetchone()
        return self._row_to_server(row) if row else None

    def get_by_name(self, name: str) -> Optional[MCPServer]:
        cursor = self.conn.execute(
            "SELECT * FROM mcp_servers WHERE name = ?", [name]
        )
        row = cursor.fetchone()
        return self._row_to_server(row) if row else None

    def get_all(self) -> list[MCPServer]:
        cursor = self.conn.execute("SELECT * FROM mcp_servers")
        return [self._row_to_server(row) for row in cursor.fetchall()]

    def update_status(self, server_id: str, status: MCPStatus) -> None:
        self.conn.execute(
            "UPDATE mcp_servers SET status = ? WHERE id = ?",
            [status.value, server_id]
        )
        self.conn.commit()

    def delete(self, server_id: str) -> bool:
        self.conn.execute("DELETE FROM mcp_servers WHERE id = ?", [server_id])
        self.conn.commit()
        return True

    def _row_to_server(self, row) -> MCPServer:
        return MCPServer(
            id=row[0],
            name=row[1],
            display_name=row[2],
            server_command=row[3],
            status=MCPStatus(row[4]),
            capabilities=json.loads(row[5]) if row[5] else []
        )


# =============================================================================
# Repository: UserSettings
# =============================================================================

class UserSettingsRepository:
    """CRUD operations for UserSettings (singleton)."""

    def __init__(self, db: Database):
        self.db = db
        self.conn = db.conn

    def get(self) -> UserSettings:
        cursor = self.conn.execute("SELECT * FROM user_settings WHERE id = 1")
        row = cursor.fetchone()
        if not row:
            return UserSettings()
        return UserSettings(
            default_input_device=row[1],
            default_output_device=row[2],
            default_brain_id=row[3],
            show_transcript=bool(row[4]),
            transcript_max_lines=row[5] or 10,
            api_key_encrypted=row[6],
            preferred_model=row[7] or "gpt-4o",
            data_directory=row[8],
            max_session_storage_days=row[9] or 30
        )

    def update(self, settings: UserSettings) -> UserSettings:
        self.conn.execute("""
            UPDATE user_settings SET
                default_input_device = ?,
                default_output_device = ?,
                default_brain_id = ?,
                show_transcript = ?,
                transcript_max_lines = ?,
                api_key_encrypted = ?,
                preferred_model = ?,
                data_directory = ?,
                max_session_storage_days = ?
            WHERE id = 1
        """, [
            settings.default_input_device,
            settings.default_output_device,
            settings.default_brain_id,
            1 if settings.show_transcript else 0,
            settings.transcript_max_lines,
            settings.api_key_encrypted,
            settings.preferred_model,
            settings.data_directory,
            settings.max_session_storage_days
        ])
        self.conn.commit()
        return settings


# =============================================================================
# RAG Service
# =============================================================================

class RAGService:
    """High-level API for RAG operations: indexing and semantic search."""

    def __init__(self, db: Database):
        self.db = db
        self.artifacts = ArtifactRepository(db)
        self.chunks = DocumentChunkRepository(db)

    def index_text(
        self,
        brain_id: str,
        filepath: str,
        text: str,
        embedding_fn,
        name: Optional[str] = None,
        chunk_size: int = 1000,
        chunk_overlap: int = 200
    ) -> Artifact:
        """Index text content into chunks with embeddings."""
        import os as _os
        artifact = Artifact(
            brain_id=brain_id,
            artifact_type=ArtifactType.FILE,
            name=name or _os.path.basename(filepath),
            metadata={"filepath": filepath},
            index_status=IndexStatus.INDEXING
        )
        self.artifacts.create(artifact)

        try:
            for i, (chunk_text, start, end) in enumerate(self._chunk_text(text, chunk_size, chunk_overlap)):
                self.chunks.create(DocumentChunk(
                    artifact_id=artifact.id,
                    filepath=filepath,
                    chunk_index=i,
                    start_char=start,
                    end_char=end,
                    text=chunk_text,
                    embedding=embedding_fn(chunk_text)
                ))
            self.artifacts.update_index_status(artifact.id, IndexStatus.INDEXED)
        except Exception as e:
            self.artifacts.update_index_status(artifact.id, IndexStatus.FAILED, str(e))
            raise

        return self.artifacts.get(artifact.id)

    def search(self, query_embedding: list[float], brain_id: Optional[str] = None, limit: int = 10) -> list[dict]:
        """Search for relevant chunks. Returns list of {chunk, similarity, artifact}."""
        results = self.chunks.search(query_embedding, limit=limit, brain_id=brain_id)
        return [
            {'chunk': chunk, 'similarity': sim, 'artifact': self.artifacts.get(chunk.artifact_id)}
            for chunk, sim in results
        ]

    def get_context(self, query_embedding: list[float], brain_id: str, max_chars: int = 16000) -> str:
        """Get formatted context string for LLM prompt."""
        results = self.search(query_embedding, brain_id=brain_id, limit=20)
        parts, total = [], 0
        for r in results:
            text = f"[{r['artifact'].name}]\n{r['chunk'].text}\n"
            if total + len(text) > max_chars:
                break
            parts.append(text)
            total += len(text)
        return "\n---\n".join(parts)

    def delete_artifact(self, artifact_id: str) -> None:
        """Delete artifact and its chunks."""
        self.chunks.delete_by_artifact(artifact_id)
        self.artifacts.delete(artifact_id)

    def _chunk_text(self, text: str, size: int, overlap: int) -> list[tuple[str, int, int]]:
        """Split text into overlapping chunks."""
        chunks, start = [], 0
        while start < len(text):
            end = min(start + size, len(text))
            if end < len(text):
                for sep in ['. ', '.\n', '! ', '? ']:
                    pos = text.rfind(sep, start, end)
                    if pos > start + size // 2:
                        end = pos + len(sep)
                        break
            chunk = text[start:end].strip()
            if chunk:
                chunks.append((chunk, start, end))
            start = end - overlap if end < len(text) else len(text)
        return chunks
