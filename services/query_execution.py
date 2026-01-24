from dataclasses import dataclass, field
from typing import Callable, Optional
import time

from models import (
    Brain, BrainTool, Interaction, AIResponse, ExecutionStep, FileReference,
    TranscriptEntry, QueryType, StepType, StepStatus, ModelConfig, ResourceType, ToolType
)
from services.database import (
    Database, BrainToolRepository, QuestionRepository,
    InteractionRepository, AIResponseRepository, ExecutionStepRepository,
    RAGService, ResourceRepository
)
from services.llm import LLMService, Message
from services.conversation import ConversationContextCache


_context_cache = ConversationContextCache()


@dataclass
class QueryContext:
    session_id: str
    brain: Brain
    query_text: str
    transcript: list[TranscriptEntry] = field(default_factory=list)
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
        self._tool_repo = BrainToolRepository(db)
        self._question_repo = QuestionRepository(db)
        self._interaction_repo = InteractionRepository(db)
        self._response_repo = AIResponseRepository(db)
        self._step_repo = ExecutionStepRepository(db)
        self._resource_repo = ResourceRepository(db)
        self._llm = LLMService(db)
        self._rag = RAGService(db)

    def execute(self, ctx: QueryContext, callbacks: ExecutionCallbacks) -> AIResponse:
        start_time = time.time()

        config = self._resolve_config(ctx)
        tools = self._tool_repo.get_enabled_by_brain(ctx.brain.id)
        interaction = self._create_interaction(ctx)

        conversation = _context_cache.get(ctx.session_id, ctx.brain.id)

        transcript_ids = []
        rag_context = ''
        file_refs = []
        resource_ids = []

        step = self._emit_step(interaction.id, StepType.LISTENING, callbacks.on_step)
        conversation.add_transcript_entries(ctx.transcript)
        transcript_ids = conversation.get_transcript_ids()
        self._complete_step(step.id, callbacks.on_step)

        has_search_tool = any(t.tool_type == ToolType.SEARCH_FILES for t in tools)
        if has_search_tool:
            linked_resources = self._resource_repo.get_by_brain(ctx.brain.id)
            folder_ids = [r.id for r in linked_resources if r.resource_type == ResourceType.FOLDER]
            if folder_ids:
                step = self._emit_step(interaction.id, StepType.SEARCHING_FILES, callbacks.on_step)
                rag_context, file_refs, resource_ids = self._gather_rag_context(folder_ids, ctx.query_text)
                self._complete_step(step.id, callbacks.on_step)

        interaction.transcript_snapshot = transcript_ids
        interaction.resources_used = resource_ids
        self._interaction_repo.update(interaction)

        system_prompt = self._build_system_prompt(ctx.brain, tools)
        messages = self._build_messages(conversation, ctx.query_text, rag_context)
        tool_defs = self._build_tools(tools)

        step = self._emit_step(interaction.id, StepType.GENERATING, callbacks.on_step)

        gen = self._llm.stream(
            messages, config, system_prompt,
            lambda delta, is_final: callbacks.on_delta(delta) if not is_final else None,
            tools=tool_defs
        )
        while True:
            try:
                delta = next(gen)
            except StopIteration as e:
                llm_response = e.value
                break
        self._complete_step(step.id, callbacks.on_step)

        conversation.add_qa(ctx.query_text, llm_response.text)

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

    def _resolve_config(self, ctx: QueryContext) -> ModelConfig:
        config = ctx.brain.default_model_config
        if ctx.question_id:
            question = self._question_repo.get(ctx.question_id)
            if question and question.model_config_override:
                config = question.model_config_override
        return config

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

    def _build_messages(self, conversation, query: str, rag_context: str) -> list[Message]:
        messages = conversation.build_messages()

        content_parts = []
        if rag_context:
            content_parts.append(f'Relevant documents:\n{rag_context}')
        content_parts.append(query)

        messages.append(Message(role='user', content='\n\n'.join(content_parts)))
        return messages

    def _build_system_prompt(self, brain: Brain, tools: list[BrainTool]) -> str:
        prompt = f'You are {brain.name}'
        if brain.description:
            prompt += f', {brain.description}'
        prompt += '.'

        if tools:
            prompt += '\n\nYou have these tools:\n'
            for tool in tools:
                prompt += f'- {tool.name}: {tool.description}\n'
            prompt += '\nUse tools when helpful. Cite sources when referencing files.'

        prompt += '\n\nAnswer based on the conversation and context. Be concise.'
        return prompt

    def _build_tools(self, tools: list[BrainTool]) -> Optional[list[dict]]:
        if not tools:
            return None

        defs = []
        for tool in tools:
            if tool.tool_type == ToolType.WEB_SEARCH:
                defs.append({'type': 'web_search'})
            elif tool.tool_type == ToolType.CODE_INTERPRETER:
                defs.append({'type': 'code_interpreter', 'container': {'type': 'auto'}})

        return defs if defs else None
