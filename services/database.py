import json
import os
import sys
from datetime import datetime, timezone
from typing import Optional

import libsql

from models import (
    Brain, Question, Resource, DocumentChunk, Session,
    TranscriptEntry, Interaction, AIResponse, ExecutionStep,
    ToolCallRecord, UserSettings, FileReference, ChatFeedItem,
    SpeakerType, QueryType, ResourceType, IndexStatus, StepType,
    StepStatus, FeedItemType
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
        Migrator(self.conn).run()


class Migrator:
    def __init__(self, conn):
        self._conn = conn
        self._migrations_dir = os.path.join(os.path.dirname(__file__), '..', 'db', 'migrations')

    def _has_column(self, table, column):
        rows = self._conn.execute(f'PRAGMA table_info({table})').fetchall()
        return any(row[1] == column for row in rows)

    def _execute_statement(self, statement):
        upper = statement.upper()
        if 'ALTER' in upper and 'ADD COLUMN' in upper:
            parts = statement.split()
            table_idx = next(i for i, p in enumerate(parts) if p.upper() == 'TABLE') + 1
            col_idx = next(i for i, p in enumerate(parts) if p.upper() == 'COLUMN') + 1
            if self._has_column(parts[table_idx], parts[col_idx]):
                return
        self._conn.execute(statement)

    def run(self):
        self._conn.execute('''
            CREATE TABLE IF NOT EXISTS _schema_migrations (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                applied_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        ''')

        has_tables = self._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='brains'"
        ).fetchone()
        applied = {row[0] for row in self._conn.execute('SELECT version FROM _schema_migrations').fetchall()}
        if has_tables and 1 not in applied:
            self._conn.execute('INSERT INTO _schema_migrations (version, name) VALUES (1, ?)', ['001_initial.sql'])
            applied.add(1)
        self._conn.commit()

        for filename in sorted(os.listdir(self._migrations_dir)):
            if not filename.endswith('.sql'):
                continue
            version = int(filename.split('_')[0])
            if version in applied:
                continue

            with open(os.path.join(self._migrations_dir, filename)) as f:
                sql = f.read()
            for statement in sql.split(';'):
                statement = statement.strip()
                if statement:
                    self._execute_statement(statement)

            self._conn.execute(
                'INSERT INTO _schema_migrations (version, name) VALUES (?, ?)',
                [version, filename]
            )
            self._conn.commit()


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
    def __init__(self, db: Database):
        self.db = db
        self.conn = db.conn

    def create(self, brain: Brain) -> Brain:
        self.conn.execute('''
            INSERT INTO brains (id, name, description, default_model_config_json,
                               template_type, system_prompt, created_at, updated_at)
            VALUES (?, ?, ?, '{}', ?, ?, ?, ?)
        ''', [
            brain.id,
            brain.name,
            brain.description,
            brain.template_type,
            brain.system_prompt,
            _dt_to_str(brain.created_at),
            _dt_to_str(brain.updated_at)
        ])
        self.conn.commit()
        return brain

    def get(self, brain_id: str) -> Optional[Brain]:
        cursor = self.conn.execute('SELECT * FROM brains WHERE id = ?', [brain_id])
        row = cursor.fetchone()
        return self._row_to_brain(row) if row else None

    def get_all(self) -> list[Brain]:
        cursor = self.conn.execute('SELECT * FROM brains ORDER BY created_at DESC')
        return [self._row_to_brain(row) for row in cursor.fetchall()]

    def update(self, brain: Brain) -> Brain:
        brain.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        self.conn.execute('''
            UPDATE brains SET name = ?, description = ?, template_type = ?,
                             system_prompt = ?, updated_at = ?
            WHERE id = ?
        ''', [
            brain.name,
            brain.description,
            brain.template_type,
            brain.system_prompt,
            _dt_to_str(brain.updated_at),
            brain.id
        ])
        self.conn.commit()
        return brain

    def delete(self, brain_id: str) -> bool:
        self.conn.execute('UPDATE sessions SET current_brain_id = NULL WHERE current_brain_id = ?', [brain_id])
        self.conn.execute('UPDATE user_settings SET default_brain_id = NULL WHERE default_brain_id = ?', [brain_id])
        self.conn.execute('DELETE FROM interactions WHERE brain_id = ?', [brain_id])
        self.conn.execute('DELETE FROM brains WHERE id = ?', [brain_id])
        self.conn.commit()
        return True

    def _row_to_brain(self, row) -> Brain:
        return Brain(
            id=row[0],
            name=row[1],
            description=row[2] or '',
            template_type=row[4],
            system_prompt=row[5] or '',
            created_at=_str_to_dt(row[6]),
            updated_at=_str_to_dt(row[7])
        )


# =============================================================================
# Repository: Questions
# =============================================================================

class QuestionRepository:
    def __init__(self, db: Database):
        self.db = db
        self.conn = db.conn

    def create(self, question: Question) -> Question:
        self.conn.execute('''
            INSERT INTO questions (id, brain_id, text, position,
                                 model_config_override_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, NULL, ?, ?)
        ''', [
            question.id,
            question.brain_id,
            question.text,
            question.position,
            _dt_to_str(question.created_at),
            _dt_to_str(question.updated_at)
        ])
        self.conn.commit()
        return question

    def get(self, question_id: str) -> Optional[Question]:
        cursor = self.conn.execute('SELECT * FROM questions WHERE id = ?', [question_id])
        row = cursor.fetchone()
        return self._row_to_question(row) if row else None

    def get_by_brain(self, brain_id: str) -> list[Question]:
        cursor = self.conn.execute(
            'SELECT * FROM questions WHERE brain_id = ? ORDER BY position',
            [brain_id]
        )
        return [self._row_to_question(row) for row in cursor.fetchall()]

    def update(self, question: Question) -> Question:
        question.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        self.conn.execute('''
            UPDATE questions SET text = ?, position = ?, updated_at = ?
            WHERE id = ?
        ''', [
            question.text,
            question.position,
            _dt_to_str(question.updated_at),
            question.id
        ])
        self.conn.commit()
        return question

    def delete(self, question_id: str) -> bool:
        self.conn.execute('DELETE FROM questions WHERE id = ?', [question_id])
        self.conn.commit()
        return True

    def _row_to_question(self, row) -> Question:
        return Question(
            id=row[0],
            brain_id=row[1],
            text=row[2],
            position=row[3],
            created_at=_str_to_dt(row[5]),
            updated_at=_str_to_dt(row[6])
        )


# =============================================================================
# Repository: Resources
# =============================================================================

class ResourceRepository:
    """CRUD operations for Resource entities."""

    def __init__(self, db: Database):
        self.db = db
        self.conn = db.conn

    def create(self, resource: Resource) -> Resource:
        self.conn.execute("""
            INSERT INTO resources (id, resource_type, name, path, size_bytes,
                                  file_count, index_status, indexed_at, index_error, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            resource.id,
            resource.resource_type.value,
            resource.name,
            resource.path,
            resource.size_bytes,
            resource.file_count,
            resource.index_status.value,
            _dt_to_str(resource.indexed_at),
            resource.index_error,
            _dt_to_str(resource.created_at)
        ])
        self.conn.commit()
        return resource

    def get(self, resource_id: str) -> Optional[Resource]:
        cursor = self.conn.execute(
            'SELECT * FROM resources WHERE id = ?', [resource_id]
        )
        row = cursor.fetchone()
        return self._row_to_resource(row) if row else None

    def get_all(self) -> list[Resource]:
        cursor = self.conn.execute('SELECT * FROM resources ORDER BY created_at DESC')
        return [self._row_to_resource(row) for row in cursor.fetchall()]

    def get_by_brain(self, brain_id: str) -> list[Resource]:
        cursor = self.conn.execute('''
            SELECT r.* FROM resources r
            JOIN brain_resources br ON br.resource_id = r.id
            WHERE br.brain_id = ?
            ORDER BY r.created_at DESC
        ''', [brain_id])
        return [self._row_to_resource(row) for row in cursor.fetchall()]

    def update(self, resource: Resource) -> Resource:
        self.conn.execute('''
            UPDATE resources SET name = ?, path = ?, size_bytes = ?,
                               file_count = ?, index_status = ?, indexed_at = ?, index_error = ?
            WHERE id = ?
        ''', [
            resource.name,
            resource.path,
            resource.size_bytes,
            resource.file_count,
            resource.index_status.value,
            _dt_to_str(resource.indexed_at),
            resource.index_error,
            resource.id
        ])
        self.conn.commit()
        return resource

    def update_index_status(self, resource_id: str, status: IndexStatus,
                           size_bytes: Optional[int] = None, file_count: Optional[int] = None,
                           error: Optional[str] = None) -> None:
        indexed_at = _dt_to_str(datetime.now(timezone.utc).replace(tzinfo=None)) if status == IndexStatus.INDEXED else None
        self.conn.execute('''
            UPDATE resources SET index_status = ?, indexed_at = ?, index_error = ?,
                               size_bytes = COALESCE(?, size_bytes),
                               file_count = COALESCE(?, file_count)
            WHERE id = ?
        ''', [status.value, indexed_at, error, size_bytes, file_count, resource_id])
        self.conn.commit()

    def delete(self, resource_id: str) -> bool:
        self.conn.execute('DELETE FROM resources WHERE id = ?', [resource_id])
        self.conn.commit()
        return True

    def link_to_brain(self, resource_id: str, brain_id: str) -> None:
        self.conn.execute('''
            INSERT OR IGNORE INTO brain_resources (brain_id, resource_id, created_at)
            VALUES (?, ?, ?)
        ''', [brain_id, resource_id, _dt_to_str(datetime.now(timezone.utc).replace(tzinfo=None))])
        self.conn.commit()

    def unlink_from_brain(self, resource_id: str, brain_id: str) -> None:
        self.conn.execute(
            'DELETE FROM brain_resources WHERE brain_id = ? AND resource_id = ?',
            [brain_id, resource_id]
        )
        self.conn.commit()

    def _row_to_resource(self, row) -> Resource:
        return Resource(
            id=row[0],
            resource_type=ResourceType(row[1]),
            name=row[2],
            path=row[3],
            size_bytes=row[4],
            file_count=row[5],
            index_status=IndexStatus(row[6]),
            indexed_at=_str_to_dt(row[7]),
            index_error=row[8],
            created_at=_str_to_dt(row[9])
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
        source_meta_json = json.dumps(chunk.source_meta) if chunk.source_meta else None
        self.conn.execute('''
            INSERT INTO document_chunks (id, resource_id, filepath, chunk_index,
                                        start_char, end_char, text, embedding,
                                        source_meta, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, vector32(?), ?, ?)
        ''', [
            chunk.id,
            chunk.resource_id,
            chunk.filepath,
            chunk.chunk_index,
            chunk.start_char,
            chunk.end_char,
            chunk.text,
            embedding_json,
            source_meta_json,
            _dt_to_str(chunk.created_at)
        ])
        self.conn.commit()
        return chunk

    def create_many(self, chunks: list[DocumentChunk]) -> None:
        for chunk in chunks:
            self.create(chunk)

    def get_by_resource(self, resource_id: str) -> list[DocumentChunk]:
        cursor = self.conn.execute(
            'SELECT id, resource_id, filepath, chunk_index, start_char, end_char, text, source_meta, created_at '
            'FROM document_chunks WHERE resource_id = ? ORDER BY chunk_index',
            [resource_id]
        )
        return [self._row_to_chunk(row) for row in cursor.fetchall()]

    def delete_by_resource(self, resource_id: str) -> None:
        self.conn.execute('DELETE FROM document_chunks WHERE resource_id = ?', [resource_id])
        self.conn.commit()

    def search(self, query_embedding: list[float], limit: int = 10,
              resource_ids: Optional[list[str]] = None) -> list[tuple[DocumentChunk, float]]:
        """Search for similar chunks using vector similarity.
        Returns list of (chunk, similarity_score) tuples."""
        embedding_json = json.dumps(query_embedding)

        if resource_ids:
            placeholders = ','.join(['?'] * len(resource_ids))
            cursor = self.conn.execute(f'''
                SELECT dc.id, dc.resource_id, dc.filepath, dc.chunk_index,
                       dc.start_char, dc.end_char, dc.text, dc.source_meta, dc.created_at,
                       vector_distance_cos(dc.embedding, vector32(?)) as distance
                FROM vector_top_k('idx_chunks_embedding', vector32(?), ?) as vtk
                JOIN document_chunks dc ON dc.rowid = vtk.id
                WHERE dc.resource_id IN ({placeholders})
                ORDER BY distance ASC
            ''', [embedding_json, embedding_json, limit * 2] + resource_ids)
        else:
            cursor = self.conn.execute('''
                SELECT dc.id, dc.resource_id, dc.filepath, dc.chunk_index,
                       dc.start_char, dc.end_char, dc.text, dc.source_meta, dc.created_at,
                       vector_distance_cos(dc.embedding, vector32(?)) as distance
                FROM vector_top_k('idx_chunks_embedding', vector32(?), ?) as vtk
                JOIN document_chunks dc ON dc.rowid = vtk.id
                ORDER BY distance ASC
            ''', [embedding_json, embedding_json, limit])

        results = []
        for row in cursor.fetchall()[:limit]:
            chunk = self._row_to_chunk(row[:9])
            similarity = 1 - row[9]
            results.append((chunk, similarity))
        return results

    def _row_to_chunk(self, row) -> DocumentChunk:
        return DocumentChunk(
            id=row[0],
            resource_id=row[1],
            filepath=row[2],
            chunk_index=row[3],
            start_char=row[4],
            end_char=row[5],
            text=row[6],
            embedding=[],
            source_meta=json.loads(row[7]) if row[7] else None,
            created_at=_str_to_dt(row[8])
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
                                is_live, current_brain_id, rating, created_at, ended_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            session.id,
            session.name,
            session.audio_input_device,
            session.audio_output_device,
            1 if session.is_live else 0,
            session.current_brain_id,
            session.rating,
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

    def get_recent_for_brain(self, brain_id: str, limit: int = 20) -> list[Session]:
        cursor = self.conn.execute(
            'SELECT * FROM sessions WHERE current_brain_id = ? ORDER BY created_at DESC LIMIT ?',
            [brain_id, limit]
        )
        return [self._row_to_session(row) for row in cursor.fetchall()]

    def delete(self, session_id: str) -> bool:
        self.conn.execute("DELETE FROM sessions WHERE id = ?", [session_id])
        self.conn.commit()
        return True

    def set_rating(self, session_id: str, rating: int) -> None:
        self.conn.execute(
            'UPDATE sessions SET rating = ? WHERE id = ?',
            [rating, session_id]
        )
        self.conn.commit()

    def _row_to_session(self, row) -> Session:
        return Session(
            id=row[0],
            name=row[1] or "",
            audio_input_device=row[2],
            audio_output_device=row[3],
            is_live=bool(row[4]),
            current_brain_id=row[5],
            rating=row[6],
            created_at=_str_to_dt(row[7]),
            ended_at=_str_to_dt(row[8])
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
        self.conn.execute('''
            INSERT INTO interactions (id, session_id, brain_id, question_id,
                                     query_type, query_text, transcript_snapshot_json,
                                     artifacts_used_json, system_prompt, tools_json,
                                     messages_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', [
            interaction.id,
            interaction.session_id,
            interaction.brain_id,
            interaction.question_id,
            interaction.query_type.value,
            interaction.query_text,
            json.dumps(interaction.transcript_snapshot),
            json.dumps(interaction.resources_used),
            interaction.system_prompt,
            json.dumps(interaction.tools) if interaction.tools is not None else None,
            json.dumps(interaction.messages) if interaction.messages is not None else None,
            _dt_to_str(interaction.created_at)
        ])
        self.conn.commit()
        return interaction

    def get(self, interaction_id: str) -> Optional[Interaction]:
        cursor = self.conn.execute(
            'SELECT * FROM interactions WHERE id = ?', [interaction_id]
        )
        row = cursor.fetchone()
        return self._row_to_interaction(row) if row else None

    def get_by_session(self, session_id: str) -> list[Interaction]:
        cursor = self.conn.execute(
            'SELECT * FROM interactions WHERE session_id = ? ORDER BY created_at',
            [session_id]
        )
        return [self._row_to_interaction(row) for row in cursor.fetchall()]

    def update(self, interaction: Interaction) -> Interaction:
        self.conn.execute('''
            UPDATE interactions SET
                transcript_snapshot_json = ?,
                artifacts_used_json = ?,
                system_prompt = ?,
                tools_json = ?,
                messages_json = ?
            WHERE id = ?
        ''', [
            json.dumps(interaction.transcript_snapshot),
            json.dumps(interaction.resources_used),
            interaction.system_prompt,
            json.dumps(interaction.tools) if interaction.tools is not None else None,
            json.dumps(interaction.messages) if interaction.messages is not None else None,
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
            resources_used=json.loads(row[7]) if row[7] else [],
            system_prompt=row[8],
            tools=json.loads(row[9]) if row[9] else None,
            messages=json.loads(row[10]) if row[10] else None,
            created_at=_str_to_dt(row[11])
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

    def update_details(self, step_id: str, details: str) -> None:
        self.conn.execute(
            'UPDATE execution_steps SET details = ? WHERE id = ?',
            [details, step_id]
        )
        self.conn.commit()

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
# Repository: ToolCalls
# =============================================================================

class ToolCallRepository:
    def __init__(self, db: Database):
        self.db = db
        self.conn = db.conn

    def create(self, record: ToolCallRecord) -> ToolCallRecord:
        self.conn.execute('''
            INSERT INTO tool_calls (id, interaction_id, call_id, tool_name,
                                    arguments_json, result, duration_ms, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', [
            record.id,
            record.interaction_id,
            record.call_id,
            record.tool_name,
            json.dumps(record.arguments),
            record.result,
            record.duration_ms,
            _dt_to_str(record.created_at)
        ])
        self.conn.commit()
        return record

    def get_by_interaction(self, interaction_id: str) -> list[ToolCallRecord]:
        cursor = self.conn.execute(
            'SELECT * FROM tool_calls WHERE interaction_id = ? ORDER BY created_at',
            [interaction_id]
        )
        return [self._row_to_record(row) for row in cursor.fetchall()]

    def _row_to_record(self, row) -> ToolCallRecord:
        return ToolCallRecord(
            id=row[0],
            interaction_id=row[1],
            call_id=row[2],
            tool_name=row[3],
            arguments=json.loads(row[4]),
            result=row[5],
            duration_ms=row[6],
            created_at=_str_to_dt(row[7])
        )


# =============================================================================
# Repository: ChatFeedItems
# =============================================================================

class ChatFeedItemRepository:
    def __init__(self, db: Database):
        self.db = db
        self.conn = db.conn

    def create(self, item: ChatFeedItem) -> ChatFeedItem:
        self.conn.execute('''
            INSERT INTO chat_feed_items (id, session_id, item_type, content,
                                         position, thread_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', [
            item.id,
            item.session_id,
            item.item_type.value,
            item.content,
            item.position,
            item.thread_id,
            _dt_to_str(item.created_at)
        ])
        self.conn.commit()
        return item

    def get_by_session(self, session_id: str) -> list[ChatFeedItem]:
        cursor = self.conn.execute(
            'SELECT * FROM chat_feed_items WHERE session_id = ? ORDER BY position',
            [session_id]
        )
        return [self._row_to_item(row) for row in cursor.fetchall()]

    def update_content(self, item_id: str, content: str) -> None:
        self.conn.execute(
            'UPDATE chat_feed_items SET content = ? WHERE id = ?',
            [content, item_id]
        )
        self.conn.commit()

    def get_next_position(self, session_id: str) -> int:
        cursor = self.conn.execute(
            'SELECT MAX(position) FROM chat_feed_items WHERE session_id = ?',
            [session_id]
        )
        row = cursor.fetchone()
        max_pos = row[0]
        return 0 if max_pos is None else max_pos + 1

    def get_session_ids_with_items(self, session_ids: list[str]) -> set[str]:
        if not session_ids:
            return set()
        placeholders = ','.join(['?'] * len(session_ids))
        cursor = self.conn.execute(
            f'SELECT DISTINCT session_id FROM chat_feed_items WHERE session_id IN ({placeholders})',
            session_ids
        )
        return {row[0] for row in cursor.fetchall()}

    def get_question_counts(self, session_ids: list[str]) -> dict[str, int]:
        if not session_ids:
            return {}
        placeholders = ','.join(['?'] * len(session_ids))
        cursor = self.conn.execute(
            f"SELECT session_id, COUNT(*) FROM chat_feed_items WHERE session_id IN ({placeholders}) AND item_type = 'question' GROUP BY session_id",
            session_ids
        )
        return {row[0]: row[1] for row in cursor.fetchall()}

    def _row_to_item(self, row) -> ChatFeedItem:
        return ChatFeedItem(
            id=row[0],
            session_id=row[1],
            item_type=FeedItemType(row[2]),
            content=row[3],
            position=row[4],
            thread_id=row[5],
            created_at=_str_to_dt(row[6])
        )


# =============================================================================
# Repository: UserSettings
# =============================================================================

class UserSettingsRepository:
    def __init__(self, db: Database):
        self.db = db
        self.conn = db.conn

    def get(self) -> UserSettings:
        cursor = self.conn.execute('SELECT * FROM user_settings WHERE id = 1')
        row = cursor.fetchone()
        if not row:
            return UserSettings()
        feedback_val = row[8]
        return UserSettings(
            default_input_device=row[1],
            default_output_device=row[2],
            default_brain_id=row[3],
            data_directory=row[5],
            max_session_storage_days=row[6] or 30,
            onboarding_complete=bool(row[7]),
            feedback_opt_in=None if feedback_val is None else bool(feedback_val)
        )

    def update(self, settings: UserSettings) -> UserSettings:
        self.conn.execute('''
            UPDATE user_settings SET
                default_input_device = ?,
                default_output_device = ?,
                default_brain_id = ?,
                preferred_model = '',
                data_directory = ?,
                max_session_storage_days = ?,
                onboarding_complete = ?,
                feedback_opt_in = ?
            WHERE id = 1
        ''', [
            settings.default_input_device,
            settings.default_output_device,
            settings.default_brain_id,
            settings.data_directory,
            settings.max_session_storage_days,
            1 if settings.onboarding_complete else 0,
            None if settings.feedback_opt_in is None else (1 if settings.feedback_opt_in else 0)
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
        self.resources = ResourceRepository(db)
        self.chunks = DocumentChunkRepository(db)

    def index_text(
        self,
        resource_id: str,
        filepath: str,
        text: str,
        embedding_fn,
        chunk_size: int = 1000,
        chunk_overlap: int = 200
    ) -> None:
        self.index_text_with_meta(resource_id, filepath, [(text, {})], embedding_fn, chunk_size, chunk_overlap)

    def index_text_with_meta(
        self,
        resource_id: str,
        filepath: str,
        segments: list[tuple[str, dict]],
        embedding_fn,
        chunk_size: int = 1000,
        chunk_overlap: int = 200
    ) -> None:
        chunk_index = 0
        for text, meta in segments:
            for chunk_text, start, end in self._chunk_text(text, chunk_size, chunk_overlap):
                self.chunks.create(DocumentChunk(
                    resource_id=resource_id,
                    filepath=filepath,
                    chunk_index=chunk_index,
                    start_char=start,
                    end_char=end,
                    text=chunk_text,
                    embedding=embedding_fn(chunk_text),
                    source_meta=meta if meta else None
                ))
                chunk_index += 1

    def search(self, query_embedding: list[float], resource_ids: Optional[list[str]] = None, limit: int = 10) -> list[dict]:
        """Search for relevant chunks. Returns list of {chunk, similarity, resource}."""
        results = self.chunks.search(query_embedding, limit=limit, resource_ids=resource_ids)
        return [
            {'chunk': chunk, 'similarity': sim, 'resource': self.resources.get(chunk.resource_id)}
            for chunk, sim in results
        ]

    def get_context(self, query_embedding: list[float], resource_ids: list[str], max_chars: int = 16000) -> str:
        """Get formatted context string for LLM prompt."""
        results = self.search(query_embedding, resource_ids=resource_ids, limit=20)
        parts, total = [], 0
        for r in results:
            text = f"[{r['resource'].name}]\n{r['chunk'].text}\n"
            if total + len(text) > max_chars:
                break
            parts.append(text)
            total += len(text)
        return '\n---\n'.join(parts)

    def delete_resource(self, resource_id: str) -> None:
        """Delete resource and its chunks."""
        self.chunks.delete_by_resource(resource_id)
        self.resources.delete(resource_id)

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
