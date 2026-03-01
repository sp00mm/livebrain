from dataclasses import dataclass, field
from typing import Callable, Optional
import base64
import mimetypes
import os
import time

from models import (
    Brain, Interaction, AIResponse, ExecutionStep, FileReference,
    TranscriptEntry, QueryType, StepType, StepStatus, ResourceType
)
from services.database import (
    Database, QuestionRepository,
    InteractionRepository, AIResponseRepository, ExecutionStepRepository,
    RAGService, ResourceRepository
)
from services.llm import LLMService, Message
from services.scanner import FileScanner
from services.conversation import ConversationContextCache


_context_cache = ConversationContextCache()

IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.ico', '.bmp'}

TOOLS = [
    {'type': 'web_search'},
    {'type': 'code_interpreter', 'container': {'type': 'auto'}},
]


@dataclass
class QueryContext:
    session_id: str
    brain: Brain
    query_text: str
    transcript: list[TranscriptEntry] = field(default_factory=list)
    query_type: QueryType = QueryType.FREEFORM
    question_id: Optional[str] = None
    conversation_snapshot: Optional[object] = None


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
        self._interaction_repo = InteractionRepository(db)
        self._response_repo = AIResponseRepository(db)
        self._step_repo = ExecutionStepRepository(db)
        self._resource_repo = ResourceRepository(db)
        self._llm = LLMService(db)
        self._rag = RAGService(db)

    def execute(self, ctx: QueryContext, callbacks: ExecutionCallbacks) -> AIResponse:
        start_time = time.time()

        interaction = self._create_interaction(ctx)
        real_cache = _context_cache.get(ctx.session_id, ctx.brain.id)

        transcript_ids = []
        rag_context = ''
        file_refs = []
        resource_ids = []

        step = self._emit_step(interaction.id, StepType.LISTENING, callbacks.on_step)
        real_cache.add_transcript_entries(ctx.transcript)
        conversation = ctx.conversation_snapshot or real_cache
        transcript_ids = conversation.get_transcript_ids()
        self._complete_step(step.id, callbacks.on_step)

        linked_resources = self._resource_repo.get_by_brain(ctx.brain.id)
        folder_ids = [r.id for r in linked_resources if r.resource_type == ResourceType.FOLDER]
        if folder_ids:
            step = self._emit_step(interaction.id, StepType.SEARCHING_FILES, callbacks.on_step)
            rag_context, file_refs, resource_ids = self._gather_rag_context(folder_ids, ctx.query_text)
            self._complete_step(step.id, callbacks.on_step)

        interaction.transcript_snapshot = transcript_ids
        interaction.resources_used = resource_ids
        self._interaction_repo.update(interaction)

        file_context = self._gather_file_context(ctx.brain.id)
        image_blocks, image_refs = self._gather_image_content(ctx.brain.id)
        file_refs.extend(image_refs)

        source_names = list(dict.fromkeys(
            [ref.display_name for ref in file_refs]
            + [r.name for r in linked_resources if r.resource_type == ResourceType.FILE]
        ))

        system_prompt = self._build_system_prompt(ctx.brain, file_context, source_names or None)
        messages = self._build_messages(conversation, ctx.query_text, rag_context, image_blocks)

        step = self._emit_step(interaction.id, StepType.GENERATING, callbacks.on_step)

        gen = self._llm.stream(
            messages, system_prompt,
            lambda delta, is_final: callbacks.on_delta(delta) if not is_final else None,
            tools=TOOLS
        )
        while True:
            try:
                delta = next(gen)
            except StopIteration as e:
                llm_response = e.value
                break
        self._complete_step(step.id, callbacks.on_step)

        real_cache.add_qa(ctx.query_text, llm_response.text)

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
        on_step(ExecutionStep(id=step_id, status=StepStatus.COMPLETED))

    def _gather_rag_context(self, resource_ids: list[str], query: str) -> tuple[str, list[FileReference], list[str]]:
        if not resource_ids:
            return '', [], []

        embedding = self.embedder.embed(query, is_query=True)
        results = self._rag.search(embedding, resource_ids=resource_ids, limit=10)

        context_parts = []
        file_refs = []
        used_resource_ids = []
        seen_resources = set()

        for r in results:
            resource = r['resource']
            chunk = r['chunk']
            similarity = r['similarity']

            context_parts.append(f'[{resource.name}]\n{chunk.text}')

            if resource.id not in seen_resources:
                seen_resources.add(resource.id)
                used_resource_ids.append(resource.id)
                file_refs.append(FileReference(
                    resource_id=resource.id,
                    filepath=chunk.filepath,
                    display_name=resource.name,
                    relevance_score=similarity
                ))

        return '\n---\n'.join(context_parts), file_refs, used_resource_ids

    def _build_messages(self, conversation, query: str, rag_context: str,
                        image_blocks: list[dict] = None) -> list[Message]:
        messages = conversation.build_messages()

        content_parts = []
        if rag_context:
            content_parts.append(f'Relevant documents:\n{rag_context}')
        content_parts.append(query)

        if image_blocks:
            content = [{'type': 'input_text', 'text': '\n\n'.join(content_parts)}]
            content.extend(image_blocks)
            messages.append(Message(role='user', content=content))
        else:
            messages.append(Message(role='user', content='\n\n'.join(content_parts)))

        return messages

    def _gather_file_context(self, brain_id: str) -> str:
        resources = self._resource_repo.get_by_brain(brain_id)
        files = [r for r in resources if r.resource_type == ResourceType.FILE]
        scanner = FileScanner()
        parts = []
        for f in files:
            ext = os.path.splitext(f.path)[1].lower()
            if ext in IMAGE_EXTENSIONS:
                continue
            content = scanner.extract_text(f.path)
            if content:
                parts.append(f'[{f.name}]\n{content}')
        return '\n---\n'.join(parts)

    def _gather_image_content(self, brain_id: str) -> tuple[list[dict], list[FileReference]]:
        resources = self._resource_repo.get_by_brain(brain_id)
        blocks = []
        refs = []
        for r in resources:
            if r.resource_type != ResourceType.FILE:
                continue
            ext = os.path.splitext(r.path)[1].lower()
            if ext not in IMAGE_EXTENSIONS:
                continue
            with open(r.path, 'rb') as f:
                b64 = base64.b64encode(f.read()).decode('utf-8')
            mime = mimetypes.guess_type(r.path)[0] or 'image/png'
            blocks.append({'type': 'input_image', 'image_url': f'data:{mime};base64,{b64}'})
            refs.append(FileReference(
                resource_id=r.id, filepath=r.path,
                display_name=r.name, relevance_score=1.0
            ))
        return blocks, refs

    def _build_system_prompt(self, brain: Brain, file_context: str = '',
                             source_names: list[str] = None) -> str:
        if brain.system_prompt:
            prompt = brain.system_prompt
        else:
            prompt = f'You are {brain.name}'
            if brain.description:
                prompt += f', {brain.description}'
            prompt += '.\n\nAnswer based on the conversation and context. Be concise.'

        if file_context:
            prompt += '\n\nHere are reference documents for this brain:\n' + file_context

        if source_names:
            names_list = ', '.join(f'[{n}]' for n in source_names)
            prompt += (
                '\n\nWhen you reference information from a specific document, '
                f'cite it inline using its filename in brackets, e.g. {names_list}. '
                'Only cite sources you actually used.'
            )

        return prompt
