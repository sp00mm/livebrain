from dataclasses import dataclass
from typing import Callable, Optional
import time

from models import (
    Brain, Interaction, AIResponse, ExecutionStep, FileReference,
    QueryType, StepType, StepStatus, ModelConfig, BrainCapabilities
)
from services.database import (
    Database, QuestionRepository, TranscriptEntryRepository,
    InteractionRepository, AIResponseRepository, ExecutionStepRepository, RAGService
)
from services.llm import LLMService, Message


@dataclass
class QueryContext:
    session_id: str
    brain: Brain
    query_text: str
    query_type: QueryType = QueryType.FREEFORM
    question_id: Optional[str] = None


@dataclass
class ExecutionCallbacks:
    on_step: Callable[[ExecutionStep], None]
    on_delta: Callable[[str], None]
    on_complete: Callable[[AIResponse], None]


class QueryExecutionService:
    def __init__(self, db: Database, embedder):
        self.db = db
        self.embedder = embedder
        self._question_repo = QuestionRepository(db)
        self._transcript_repo = TranscriptEntryRepository(db)
        self._interaction_repo = InteractionRepository(db)
        self._response_repo = AIResponseRepository(db)
        self._step_repo = ExecutionStepRepository(db)
        self._llm = LLMService(db)
        self._rag = RAGService(db)

    def execute(self, ctx: QueryContext, callbacks: ExecutionCallbacks) -> AIResponse:
        start_time = time.time()

        config, capabilities = self._resolve_config(ctx)
        interaction = self._create_interaction(ctx)

        transcript_text = ''
        rag_context = ''
        file_refs = []
        transcript_ids = []
        artifact_ids = []

        if capabilities.conversation:
            step = self._emit_step(interaction.id, StepType.LISTENING, callbacks.on_step)
            transcript_text, transcript_ids = self._gather_transcript(ctx.session_id)
            self._complete_step(step.id, callbacks.on_step)

        if capabilities.files:
            step = self._emit_step(interaction.id, StepType.SEARCHING_FILES, callbacks.on_step)
            rag_context, file_refs, artifact_ids = self._gather_rag_context(ctx.brain.id, ctx.query_text)
            self._complete_step(step.id, callbacks.on_step)

        # Update interaction with context snapshots
        interaction.transcript_snapshot = transcript_ids
        interaction.artifacts_used = artifact_ids
        self._interaction_repo.update(interaction)

        messages = self._build_messages(ctx.query_text, transcript_text, rag_context)
        system_prompt = self._build_system_prompt(ctx.brain)

        step = self._emit_step(interaction.id, StepType.GENERATING, callbacks.on_step)
        full_text = ''

        gen = self._llm.stream(
            messages, config, system_prompt,
            lambda delta, is_final: callbacks.on_delta(delta) if not is_final else None
        )
        while True:
            try:
                delta = next(gen)
                full_text += delta
            except StopIteration as e:
                llm_response = e.value
                break
        self._complete_step(step.id, callbacks.on_step)

        latency_ms = int((time.time() - start_time) * 1000)
        response = AIResponse(
            interaction_id=interaction.id,
            text=llm_response.text,
            file_references=file_refs,
            model_used=llm_response.model,
            tokens_input=llm_response.tokens_input,
            tokens_output=llm_response.tokens_output,
            latency_ms=latency_ms
        )
        self._response_repo.create(response)
        callbacks.on_complete(response)
        return response

    def _resolve_config(self, ctx: QueryContext) -> tuple[ModelConfig, BrainCapabilities]:
        config = ctx.brain.default_model_config
        capabilities = ctx.brain.capabilities

        if ctx.question_id:
            question = self._question_repo.get(ctx.question_id)
            if question and question.model_config_override:
                config = question.model_config_override
            if question and question.capabilities_override:
                capabilities = question.capabilities_override

        return config, capabilities

    def _create_interaction(self, ctx: QueryContext) -> Interaction:
        interaction = Interaction(
            session_id=ctx.session_id,
            brain_id=ctx.brain.id,
            question_id=ctx.question_id,
            query_type=ctx.query_type,
            query_text=ctx.query_text
        )
        return self._interaction_repo.create(interaction)

    def _emit_step(self, interaction_id: str, step_type: StepType,
                   on_step: Callable[[ExecutionStep], None]) -> ExecutionStep:
        step = ExecutionStep(interaction_id=interaction_id, step_type=step_type)
        self._step_repo.create(step)
        on_step(step)
        return step

    def _complete_step(self, step_id: str, on_step: Callable[[ExecutionStep], None]):
        self._step_repo.complete(step_id)
        # Emit a minimal step object to signal completion
        on_step(ExecutionStep(id=step_id, status=StepStatus.COMPLETED))

    def _gather_transcript(self, session_id: str, max_lines: int = 20) -> tuple[str, list[str]]:
        entries = self._transcript_repo.get_recent(session_id, max_lines)
        lines = [f'{e.speaker.value}: {e.text}' for e in entries]
        ids = [e.id for e in entries]
        return '\n'.join(lines), ids

    def _gather_rag_context(self, brain_id: str, query: str) -> tuple[str, list[FileReference], list[str]]:
        embedding = self.embedder.embed(query, is_query=True)
        results = self._rag.search(embedding, brain_id=brain_id, limit=10)

        context_parts = []
        file_refs = []
        artifact_ids = []
        seen_artifacts = set()

        for r in results:
            artifact = r['artifact']
            chunk = r['chunk']
            similarity = r['similarity']

            context_parts.append(f'[{artifact.name}]\n{chunk.text}')

            if artifact.id not in seen_artifacts:
                seen_artifacts.add(artifact.id)
                artifact_ids.append(artifact.id)
                file_refs.append(FileReference(
                    artifact_id=artifact.id,
                    filepath=chunk.filepath,
                    display_name=artifact.name,
                    relevance_score=similarity
                ))

        return '\n---\n'.join(context_parts), file_refs, artifact_ids

    def _build_messages(self, query: str, transcript: str, rag_context: str) -> list[Message]:
        content_parts = []

        if transcript:
            content_parts.append(f'Conversation transcript:\n{transcript}')

        if rag_context:
            content_parts.append(f'Relevant documents:\n{rag_context}')

        content_parts.append(f'Question: {query}')

        return [Message(role='user', content='\n\n'.join(content_parts))]

    def _build_system_prompt(self, brain: Brain) -> str:
        prompt = f'You are {brain.name}, an AI assistant.'
        if brain.description:
            prompt += f'\n{brain.description}'
        prompt += '\n\nAnswer questions based on the provided context. Reference files when relevant.'
        return prompt
