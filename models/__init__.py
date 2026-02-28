"""
Livebrain Data Models

Core entities for brains, sessions, transcripts, and AI interactions.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
import uuid


def generate_id() -> str:
    return str(uuid.uuid4())


def now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# =============================================================================
# Enums
# =============================================================================

class SpeakerType(Enum):
    USER = 'user'      # Microphone (you)
    OTHER = 'other'    # System audio (them)


class QueryType(Enum):
    PRESET = 'preset'      # Clicked a question
    FREEFORM = 'freeform'  # Typed in input box


class ResourceType(Enum):
    FILE = 'file'      # Images + PDFs - direct LLM upload, NO RAG
    FOLDER = 'folder'  # RAG-scanned with embeddings


class IndexStatus(Enum):
    PENDING = 'pending'
    INDEXING = 'indexing'
    INDEXED = 'indexed'
    FAILED = 'failed'


class StepType(Enum):
    LISTENING = 'listening'
    SEARCHING_FILES = 'searching_files'
    GENERATING = 'generating'


class StepStatus(Enum):
    IN_PROGRESS = 'in_progress'
    COMPLETED = 'completed'
    FAILED = 'failed'


# =============================================================================
# Core Entities
# =============================================================================

@dataclass
class Brain:
    id: str = field(default_factory=generate_id)
    name: str = ''
    description: str = ''
    template_type: str | None = None
    system_prompt: str = ''
    created_at: datetime = field(default_factory=now)
    updated_at: datetime = field(default_factory=now)


@dataclass
class Question:
    id: str = field(default_factory=generate_id)
    brain_id: str = ''
    text: str = ''
    position: int = 0
    created_at: datetime = field(default_factory=now)
    updated_at: datetime = field(default_factory=now)


@dataclass
class Resource:
    id: str = field(default_factory=generate_id)
    resource_type: ResourceType = ResourceType.FILE
    name: str = ''
    path: str = ''
    size_bytes: Optional[int] = None
    file_count: Optional[int] = None
    index_status: IndexStatus = IndexStatus.PENDING
    indexed_at: Optional[datetime] = None
    index_error: Optional[str] = None
    created_at: datetime = field(default_factory=now)

    @property
    def size_mb(self) -> float:
        return (self.size_bytes or 0) / (1024 * 1024)


@dataclass
class DocumentChunk:
    id: str = field(default_factory=generate_id)
    resource_id: str = ''
    filepath: str = ''
    chunk_index: int = 0
    start_char: int = 0
    end_char: int = 0
    text: str = ''
    embedding: list[float] = field(default_factory=list)
    created_at: datetime = field(default_factory=now)


@dataclass
class Session:
    id: str = field(default_factory=generate_id)
    name: str = ""
    audio_input_device: Optional[str] = None
    audio_output_device: Optional[str] = None
    is_live: bool = False
    current_brain_id: Optional[str] = None
    created_at: datetime = field(default_factory=now)
    ended_at: Optional[datetime] = None


@dataclass
class TranscriptEntry:
    id: str = field(default_factory=generate_id)
    session_id: str = ""
    speaker: SpeakerType = SpeakerType.USER
    text: str = ""
    confidence: float = 1.0
    timestamp: datetime = field(default_factory=now)


@dataclass
class Interaction:
    id: str = field(default_factory=generate_id)
    session_id: str = ''
    brain_id: str = ''
    question_id: Optional[str] = None
    query_type: QueryType = QueryType.FREEFORM
    query_text: str = ''
    transcript_snapshot: list[str] = field(default_factory=list)
    resources_used: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=now)


@dataclass
class FileReference:
    resource_id: str = ''
    filepath: str = ''
    display_name: str = ''
    relevance_score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            'resource_id': self.resource_id,
            'filepath': self.filepath,
            'display_name': self.display_name,
            'relevance_score': self.relevance_score
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'FileReference':
        return cls(
            resource_id=data.get('resource_id', ''),
            filepath=data.get('filepath', ''),
            display_name=data.get('display_name', ''),
            relevance_score=data.get('relevance_score', 0.0)
        )


@dataclass
class AIResponse:
    id: str = field(default_factory=generate_id)
    interaction_id: str = ""
    text: str = ""
    file_references: list[FileReference] = field(default_factory=list)
    model_used: str = ""
    tokens_input: int = 0
    tokens_output: int = 0
    latency_ms: int = 0
    created_at: datetime = field(default_factory=now)


@dataclass
class ExecutionStep:
    id: str = field(default_factory=generate_id)
    interaction_id: str = ""
    step_type: StepType = StepType.GENERATING
    status: StepStatus = StepStatus.IN_PROGRESS
    details: Optional[str] = None
    started_at: datetime = field(default_factory=now)
    completed_at: Optional[datetime] = None


@dataclass
class UserSettings:
    default_input_device: Optional[str] = None
    default_output_device: Optional[str] = None
    default_brain_id: Optional[str] = None
    data_directory: Optional[str] = None
    max_session_storage_days: int = 30
    onboarding_complete: bool = False
