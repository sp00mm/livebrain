from dataclasses import dataclass, field
from typing import Callable, Optional
import base64
import json
import mimetypes
import os
import time

from models import (
    Brain, Interaction, AIResponse, ExecutionStep, FileReference,
    TranscriptEntry, ToolCallRecord, QueryType, StepType, StepStatus,
    ResourceType, ToolCallDetail
)
from services.database import (
    Database, QuestionRepository,
    InteractionRepository, AIResponseRepository, ExecutionStepRepository,
    ToolCallRepository, RAGService, ResourceRepository
)
from services.llm import LLMService, Message
from services.scanner import FileScanner
from services.conversation import ConversationContextCache
from services.tools import REGISTRY, ToolContext, ToolResult
from services.prompt import SystemPromptBuilder


_context_cache = ConversationContextCache()

IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.ico', '.bmp'}

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
    on_tool_call: Callable


class QueryExecutionService:
    def __init__(self, db: Database, embedder):
        self.db = db
        self.embedder = embedder
        self._question_repo = QuestionRepository(db)
        self._interaction_repo = InteractionRepository(db)
        self._response_repo = AIResponseRepository(db)
        self._step_repo = ExecutionStepRepository(db)
        self._resource_repo = ResourceRepository(db)
        self._tool_call_repo = ToolCallRepository(db)
        self._llm = LLMService(db)
        self._rag = RAGService(db)

    def execute(self, ctx: QueryContext, callbacks: ExecutionCallbacks) -> AIResponse:
        start_time = time.time()

        interaction = self._create_interaction(ctx)
        real_cache = _context_cache.get(ctx.session_id, ctx.brain.id)

        file_refs = []
        resource_ids = []

        step = self._emit_step(interaction.id, StepType.LISTENING, callbacks.on_step)
        real_cache.add_transcript_entries(ctx.transcript)
        conversation = ctx.conversation_snapshot or real_cache
        transcript_ids = conversation.get_transcript_ids()
        self._complete_step(step.id, callbacks.on_step)

        linked_resources = self._resource_repo.get_by_brain(ctx.brain.id)
        folder_resources = [r for r in linked_resources if r.resource_type == ResourceType.FOLDER]
        folder_ids = [r.id for r in folder_resources]
        file_tree = _build_file_tree(folder_resources)

        interaction.transcript_snapshot = transcript_ids

        file_context = self._gather_file_context(ctx.brain.id)
        image_blocks, image_refs = self._gather_image_content(ctx.brain.id)
        file_refs.extend(image_refs)

        tool_ctx = ToolContext(
            folder_ids=folder_ids,
            embedder=self.embedder,
            rag=self._rag,
            scanner=FileScanner(),
            folder_paths=[r.path for r in folder_resources],
        )
        tools = REGISTRY.build_schemas(tool_ctx)
        interaction.tools = tools
        messages = self._build_messages(conversation, ctx.query_text, image_blocks)
        interaction.messages = [{'role': m.role, 'content': m.content} for m in messages]

        extra_input = []
        total_input_tokens = 0
        total_output_tokens = 0

        available_tools = REGISTRY.get_available(tool_ctx)

        for _ in range(5):
            source_names = list(dict.fromkeys(
                [ref.display_name for ref in file_refs]
                + [r.name for r in linked_resources if r.resource_type == ResourceType.FILE]
            ))
            system_prompt = (
                SystemPromptBuilder()
                .identity(ctx.brain)
                .template_context(ctx.brain)
                .transcript_note()
                .capabilities(available_tools, has_folders=bool(folder_ids))
                .file_tree(file_tree)
                .file_context(file_context)
                .citations(source_names or None)
                .rules()
                .build()
            )
            interaction.system_prompt = system_prompt

            step = self._emit_step(interaction.id, StepType.GENERATING, callbacks.on_step)
            llm_response = self._call_llm(messages, system_prompt, tools, extra_input, callbacks.on_delta)
            self._complete_step(step.id, callbacks.on_step)

            total_input_tokens += llm_response.tokens_input
            total_output_tokens += llm_response.tokens_output

            if not llm_response.tool_calls:
                break

            for item in llm_response.output_items:
                extra_input.append(item.model_dump())

            for tc in llm_response.tool_calls:
                output = self._run_tool_call(tc, tool_ctx, callbacks, interaction.id, file_refs, resource_ids)
                extra_input.append(output)

        interaction.resources_used = resource_ids
        self._interaction_repo.update(interaction)

        real_cache.add_qa(ctx.query_text, llm_response.text)

        latency_ms = int((time.time() - start_time) * 1000)
        response = AIResponse(
            interaction_id=interaction.id,
            text=llm_response.text,
            file_references=file_refs,
            model_used=llm_response.model,
            tokens_input=total_input_tokens,
            tokens_output=total_output_tokens,
            latency_ms=latency_ms
        )
        self._response_repo.create(response)
        callbacks.on_complete(response)
        return response

    def _call_llm(self, messages, system_prompt, tools, extra_input, on_delta):
        gen = self._llm.stream(
            messages, system_prompt,
            lambda delta, is_final: on_delta(delta) if not is_final else None,
            tools=tools, extra_input=extra_input or None
        )
        while True:
            try:
                next(gen)
            except StopIteration as e:
                return e.value

    def _run_tool_call(self, tc, tool_ctx, callbacks, interaction_id, file_refs, resource_ids):
        tool = REGISTRY.get(tc.name)
        step = self._emit_step(interaction_id, tool.step_type, callbacks.on_step)
        tool_start = time.time()
        args = json.loads(tc.arguments)
        result = tool.handler(args, tool_ctx)
        tool_duration = int((time.time() - tool_start) * 1000)
        file_refs.extend(result.file_refs)
        resource_ids.extend(result.resource_ids)
        details = json.dumps({
            'query': args.get('query', ''),
            'matched_files': [r.display_name for r in result.file_refs]
        })
        self._step_repo.update_details(step.id, details)
        self._complete_step(step.id, callbacks.on_step)

        callbacks.on_tool_call(ToolCallDetail(
            summary=result.summary,
            details=result.details + [(f'{tool_duration}ms', '')],
        ))

        self._tool_call_repo.create(ToolCallRecord(
            interaction_id=interaction_id,
            call_id=tc.call_id,
            tool_name=tc.name,
            arguments=args,
            result=result.output,
            duration_ms=tool_duration
        ))

        return {
            'type': 'function_call_output',
            'call_id': tc.call_id,
            'output': result.output
        }

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

    def _build_messages(self, conversation, query: str,
                        image_blocks: list[dict] = None) -> list[Message]:
        messages = conversation.build_messages()
        if image_blocks:
            content = [{'type': 'input_text', 'text': query}]
            content.extend(image_blocks)
            messages.append(Message(role='user', content=content))
        else:
            messages.append(Message(role='user', content=query))
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

def _build_file_tree(folder_resources):
    scanner = FileScanner()
    lines = []
    for resource in folder_resources:
        if not os.path.isdir(resource.path):
            continue
        lines.append(f'{resource.name}/')
        files = scanner.scan_directory(resource.path)
        rel_paths = sorted(os.path.relpath(f, resource.path) for f in files[:50])
        for rel in rel_paths:
            lines.append(f'  {rel}')
        if len(files) > 50:
            lines.append(f'  ... and {len(files) - 50} more files')
    return '\n'.join(lines) if lines else None
