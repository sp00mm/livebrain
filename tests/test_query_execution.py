import json
import os
import struct
import tempfile
import zlib
from unittest.mock import patch, MagicMock

import pytest

from models import (
    Brain, Question, Session, TranscriptEntry, Interaction, AIResponse, ExecutionStep,
    FileReference, Resource, ResourceType, IndexStatus,
    QueryType, StepType, StepStatus, SpeakerType, ToolCallRecord
)
from services.database import (
    BrainRepository, QuestionRepository, SessionRepository,
    TranscriptEntryRepository, InteractionRepository, ResourceRepository,
    ToolCallRepository, RAGService
)
from services.query_execution import QueryExecutionService, QueryContext, ExecutionCallbacks
from services.tools import REGISTRY, ToolContext
from services.conversation import ConversationContext
from services.llm import LLMResponse, ToolCall


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
            on_complete=lambda r: None,
            on_tool_call=lambda d: None
        )
        assert callable(callbacks.on_step)
        assert callable(callbacks.on_delta)
        assert callable(callbacks.on_complete)
        assert callable(callbacks.on_tool_call)


class TestQueryExecutionService:
    def test_init(self, db):
        service = QueryExecutionService(db, MockEmbedder())
        assert service.db == db
        assert service.embedder is not None

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

    def test_build_system_prompt_default(self, db):
        service = QueryExecutionService(db, MockEmbedder())
        brain = Brain(name='Interview Helper', description='Helps with interviews')

        prompt = service._build_system_prompt(brain)

        assert 'Interview Helper' in prompt
        assert 'Helps with interviews' in prompt

    def test_build_system_prompt_custom(self, db):
        service = QueryExecutionService(db, MockEmbedder())
        brain = Brain(name='Test', system_prompt='You are a custom assistant.')

        prompt = service._build_system_prompt(brain)

        assert 'You are a custom assistant.' in prompt


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


class TestBuildSystemPromptWithFileContext:
    def test_default_prompt_with_file_context(self, db):
        service = QueryExecutionService(db, MockEmbedder())
        brain = Brain(name='Interview Helper', description='Helps with interviews')

        prompt = service._build_system_prompt(brain, 'some file content')

        assert 'Interview Helper' in prompt
        assert 'Helps with interviews' in prompt
        assert 'Reference documents' in prompt
        assert 'some file content' in prompt

    def test_custom_prompt_with_file_context(self, db):
        service = QueryExecutionService(db, MockEmbedder())
        brain = Brain(name='Test', system_prompt='You are a custom assistant.')

        prompt = service._build_system_prompt(brain, 'doc text')

        assert 'You are a custom assistant.' in prompt
        assert 'Reference documents' in prompt
        assert 'doc text' in prompt

    def test_empty_file_context_not_appended(self, db):
        service = QueryExecutionService(db, MockEmbedder())
        brain = Brain(name='Test', description='A test brain')

        prompt = service._build_system_prompt(brain, '')

        assert 'Reference documents' not in prompt


class TestGatherFileContext:
    def test_gather_text_files(self, db):
        brain_repo = BrainRepository(db)
        resource_repo = ResourceRepository(db)
        brain = brain_repo.create(Brain(name='Test'))

        with tempfile.NamedTemporaryFile(suffix='.txt', mode='w', delete=False) as f:
            f.write('Hello from test file')
            tmp_path = f.name

        resource = resource_repo.create(Resource(
            resource_type=ResourceType.FILE, name='test.txt', path=tmp_path
        ))
        resource_repo.link_to_brain(resource.id, brain.id)

        service = QueryExecutionService(db, MockEmbedder())
        result = service._gather_file_context(brain.id)

        assert 'Hello from test file' in result
        os.unlink(tmp_path)

    def test_gather_skips_images(self, db):
        brain_repo = BrainRepository(db)
        resource_repo = ResourceRepository(db)
        brain = brain_repo.create(Brain(name='Test'))

        resource = resource_repo.create(Resource(
            resource_type=ResourceType.FILE, name='photo.png', path='/fake/image.png'
        ))
        resource_repo.link_to_brain(resource.id, brain.id)

        service = QueryExecutionService(db, MockEmbedder())
        result = service._gather_file_context(brain.id)

        assert result == ''

    def test_gather_multiple_files(self, db):
        brain_repo = BrainRepository(db)
        resource_repo = ResourceRepository(db)
        brain = brain_repo.create(Brain(name='Test'))

        paths = []
        for i, content in enumerate(['First file content', 'Second file content']):
            with tempfile.NamedTemporaryFile(suffix='.txt', mode='w', delete=False) as f:
                f.write(content)
                paths.append(f.name)
            resource = resource_repo.create(Resource(
                resource_type=ResourceType.FILE, name=f'file{i}.txt', path=f.name
            ))
            resource_repo.link_to_brain(resource.id, brain.id)

        service = QueryExecutionService(db, MockEmbedder())
        result = service._gather_file_context(brain.id)

        assert 'First file content' in result
        assert 'Second file content' in result
        assert '---' in result

        for p in paths:
            os.unlink(p)


class TestImageContent:
    def _create_tiny_png(self, path):
        sig = b'\x89PNG\r\n\x1a\n'
        ihdr_data = struct.pack('>IIBBBBB', 1, 1, 8, 2, 0, 0, 0)
        ihdr_crc = zlib.crc32(b'IHDR' + ihdr_data) & 0xffffffff
        ihdr = struct.pack('>I', 13) + b'IHDR' + ihdr_data + struct.pack('>I', ihdr_crc)
        raw = b'\x00\x00\x00\x00'
        compressed = zlib.compress(raw)
        idat_crc = zlib.crc32(b'IDAT' + compressed) & 0xffffffff
        idat = struct.pack('>I', len(compressed)) + b'IDAT' + compressed + struct.pack('>I', idat_crc)
        iend_crc = zlib.crc32(b'IEND') & 0xffffffff
        iend = struct.pack('>I', 0) + b'IEND' + struct.pack('>I', iend_crc)
        with open(path, 'wb') as f:
            f.write(sig + ihdr + idat + iend)

    def test_gather_image_content(self, db, tmp_path):
        brain_repo = BrainRepository(db)
        resource_repo = ResourceRepository(db)
        brain = brain_repo.create(Brain(name='Test'))

        png_path = str(tmp_path / 'photo.png')
        self._create_tiny_png(png_path)

        resource = Resource(
            resource_type=ResourceType.FILE,
            name='photo.png',
            path=png_path,
            index_status=IndexStatus.INDEXED
        )
        resource_repo.create(resource)
        resource_repo.link_to_brain(resource.id, brain.id)

        service = QueryExecutionService(db, MockEmbedder())
        blocks, refs = service._gather_image_content(brain.id)
        assert len(blocks) == 1
        assert blocks[0]['type'] == 'input_image'
        assert 'data:image/png;base64,' in blocks[0]['image_url']
        assert len(refs) == 1
        assert refs[0].display_name == 'photo.png'

    def test_gather_image_skips_text(self, db, tmp_path):
        brain_repo = BrainRepository(db)
        resource_repo = ResourceRepository(db)
        brain = brain_repo.create(Brain(name='Test'))

        txt_path = str(tmp_path / 'notes.txt')
        with open(txt_path, 'w') as f:
            f.write('hello')

        resource = Resource(
            resource_type=ResourceType.FILE,
            name='notes.txt',
            path=txt_path,
            index_status=IndexStatus.INDEXED
        )
        resource_repo.create(resource)
        resource_repo.link_to_brain(resource.id, brain.id)

        service = QueryExecutionService(db, MockEmbedder())
        blocks, refs = service._gather_image_content(brain.id)
        assert len(blocks) == 0
        assert len(refs) == 0

    def test_build_messages_with_images(self, db):
        service = QueryExecutionService(db, MockEmbedder())
        conv = ConversationContext(session_id='s1', brain_id='b1')
        image_blocks = [{'type': 'input_image', 'image_url': 'data:image/png;base64,abc'}]
        messages = service._build_messages(conv, 'describe this', image_blocks)
        assert isinstance(messages[-1].content, list)
        assert messages[-1].content[0]['type'] == 'input_text'
        assert messages[-1].content[1]['type'] == 'input_image'

    def test_build_messages_without_images(self, db):
        service = QueryExecutionService(db, MockEmbedder())
        conv = ConversationContext(session_id='s1', brain_id='b1')
        messages = service._build_messages(conv, 'hello')
        assert isinstance(messages[-1].content, str)


class TestSourceCitations:
    def test_system_prompt_with_source_names(self, db):
        service = QueryExecutionService(db, MockEmbedder())
        brain = Brain(name='Test', description='helper')
        prompt = service._build_system_prompt(brain, '', ['report.pdf', 'notes.txt'])
        assert 'report.pdf' in prompt
        assert 'notes.txt' in prompt
        assert 'markdown link format' in prompt

    def test_system_prompt_without_source_names(self, db):
        service = QueryExecutionService(db, MockEmbedder())
        brain = Brain(name='Test', description='helper')
        prompt = service._build_system_prompt(brain, '')
        assert 'markdown link format' not in prompt

    def test_system_prompt_with_none_source_names(self, db):
        service = QueryExecutionService(db, MockEmbedder())
        brain = Brain(name='Test', description='helper')
        prompt = service._build_system_prompt(brain, '', None)
        assert 'markdown link format' not in prompt

    def test_citation_rules_markdown_format(self, db):
        service = QueryExecutionService(db, MockEmbedder())
        brain = Brain(name='Test', description='helper')
        prompt = service._build_system_prompt(brain, '', ['report.pdf', 'notes.txt'])
        assert 'markdown link format' in prompt
        assert '[relevant quote](report.pdf)' in prompt
        assert 'Available sources: report.pdf, notes.txt' in prompt

    def test_tool_results_include_source_meta(self, db):
        brain_repo = BrainRepository(db)
        resource_repo = ResourceRepository(db)
        brain = brain_repo.create(Brain(name='Test'))

        resource = resource_repo.create(Resource(
            resource_type=ResourceType.FOLDER, name='docs', path='/tmp/docs'
        ))
        resource_repo.link_to_brain(resource.id, brain.id)


        embedder = MockEmbedder()
        tool_ctx = ToolContext(
            folder_ids=[resource.id], embedder=embedder,
            rag=RAGService(db), scanner=None, folder_paths=['/tmp/docs'],
        )
        tool = REGISTRY.get('search_files')
        result = tool.handler({'query': 'test'}, tool_ctx)
        parsed = json.loads(result.output)
        assert isinstance(parsed, list)
        assert len(parsed) == 0


class TestFileReferenceSourceMeta:
    def test_file_reference_with_source_meta(self):
        ref = FileReference(
            resource_id='r1', filepath='/tmp/report.pdf',
            display_name='report.pdf', relevance_score=0.95,
            source_meta={'page': 3}
        )
        d = ref.to_dict()
        assert d['source_meta'] == {'page': 3}

    def test_file_reference_without_source_meta(self):
        ref = FileReference(
            resource_id='r1', filepath='/tmp/report.pdf',
            display_name='report.pdf', relevance_score=0.95
        )
        d = ref.to_dict()
        assert 'source_meta' not in d

    def test_file_reference_from_dict_with_source_meta(self):
        data = {
            'resource_id': 'r1',
            'filepath': '/tmp/report.pdf',
            'display_name': 'report.pdf',
            'relevance_score': 0.95,
            'source_meta': {'page': 5}
        }
        ref = FileReference.from_dict(data)
        assert ref.source_meta == {'page': 5}

    def test_file_reference_from_dict_without_source_meta(self):
        data = {
            'resource_id': 'r1',
            'filepath': '/tmp/report.pdf',
            'display_name': 'report.pdf',
            'relevance_score': 0.95
        }
        ref = FileReference.from_dict(data)
        assert ref.source_meta is None


class TestRichSystemPrompt:
    def test_prompt_contains_livebrain_identity(self, db):
        service = QueryExecutionService(db, MockEmbedder())
        brain = Brain(name='Test')
        prompt = service._build_system_prompt(brain)
        assert 'Livebrain' in prompt

    def test_prompt_contains_transcript_warning(self, db):
        service = QueryExecutionService(db, MockEmbedder())
        brain = Brain(name='Test')
        prompt = service._build_system_prompt(brain)
        assert 'speech recognition' in prompt

    def test_prompt_contains_tool_descriptions(self, db):
        service = QueryExecutionService(db, MockEmbedder())
        brain = Brain(name='Test')
        prompt = service._build_system_prompt(brain, has_folders=True)
        assert 'Search files' in prompt

    def test_prompt_contains_behavioral_rules(self, db):
        service = QueryExecutionService(db, MockEmbedder())
        brain = Brain(name='Test')
        prompt = service._build_system_prompt(brain)
        assert 'Be concise' in prompt

    def test_prompt_with_file_tree(self, db):
        service = QueryExecutionService(db, MockEmbedder())
        brain = Brain(name='Test')
        prompt = service._build_system_prompt(brain, file_tree='project/\n  main.py\n  utils.py')
        assert 'Available files' in prompt
        assert 'main.py' in prompt

    def test_prompt_without_file_tree(self, db):
        service = QueryExecutionService(db, MockEmbedder())
        brain = Brain(name='Test')
        prompt = service._build_system_prompt(brain)
        assert 'Directory structure' not in prompt

    def test_prompt_with_template_context(self, db):
        service = QueryExecutionService(db, MockEmbedder())
        brain = Brain(name='Interview', template_type='interview')
        prompt = service._build_system_prompt(brain)
        assert 'interviewer' in prompt
        assert 'red flags' in prompt


class TestToolCallDetail:
    def test_dataclass(self):
        from models import ToolCallDetail
        detail = ToolCallDetail(
            summary='Searched: "revenue growth"',
            details=[('Found in', 'report.pdf, notes.txt'), ('5 results', '')],
        )
        assert detail.summary == 'Searched: "revenue growth"'
        assert len(detail.details) == 2

    def test_defaults(self):
        from models import ToolCallDetail
        detail = ToolCallDetail()
        assert detail.summary == ''
        assert detail.details == []


class TestToolExecution:
    def test_build_schemas_with_folders(self, db):

        ctx = ToolContext(
            folder_ids=['folder-1', 'folder-2'], embedder=MockEmbedder(),
            rag=RAGService(db), scanner=None, folder_paths=[],
        )
        tools = REGISTRY.build_schemas(ctx)
        names = [t.get('name') for t in tools if t.get('name')]
        assert 'search_files' in names
        assert any(t['type'] == 'web_search' for t in tools)

    def test_build_schemas_without_folders(self, db):

        ctx = ToolContext(
            folder_ids=[], embedder=MockEmbedder(),
            rag=RAGService(db), scanner=None, folder_paths=[],
        )
        tools = REGISTRY.build_schemas(ctx)
        names = [t.get('name') for t in tools if t.get('name')]
        assert 'search_files' not in names
        assert any(t['type'] == 'web_search' for t in tools)

    def test_search_files_handler(self, db):

        ctx = ToolContext(
            folder_ids=[], embedder=MockEmbedder(),
            rag=RAGService(db), scanner=None, folder_paths=[],
        )
        tool = REGISTRY.get('search_files')
        result = tool.handler({'query': 'test query'}, ctx)
        assert isinstance(result.output, str)
        assert isinstance(result.file_refs, list)
        assert isinstance(result.resource_ids, list)

    def test_registry_get_unknown(self):
        with pytest.raises(KeyError):
            REGISTRY.get('nonexistent_tool')

    def test_build_messages_simplified(self, db):
        service = QueryExecutionService(db, MockEmbedder())
        conv = ConversationContext(session_id='s1', brain_id='b1')
        messages = service._build_messages(conv, 'hello')
        assert messages[-1].content == 'hello'
        assert messages[-1].role == 'user'


def _fake_stream_no_tools(*args, **kwargs):
    yield ''
    return LLMResponse(text='answer', model='test-model', tokens_input=10, tokens_output=5)


def _fake_stream_with_tool_call(*args, **kwargs):
    call_count = getattr(_fake_stream_with_tool_call, '_call_count', 0)
    _fake_stream_with_tool_call._call_count = call_count + 1
    if call_count == 0:
        yield ''
        output_item = MagicMock()
        output_item.model_dump.return_value = {'type': 'function_call', 'name': 'search_files'}
        return LLMResponse(
            text='', model='test-model', tokens_input=5, tokens_output=3,
            tool_calls=[ToolCall(call_id='tc-1', name='search_files', arguments='{"query": "test"}')],
            output_items=[output_item]
        )
    else:
        yield ''
        return LLMResponse(text='found it', model='test-model', tokens_input=8, tokens_output=4)


class TestExecutionTrace:
    def _setup(self, db):
        brain_repo = BrainRepository(db)
        session_repo = SessionRepository(db)
        brain = brain_repo.create(Brain(name='Test'))
        session = session_repo.create(Session(name='Session'))
        return brain, session

    def _callbacks(self):
        return ExecutionCallbacks(
            on_step=lambda s: None,
            on_delta=lambda d: None,
            on_complete=lambda r: None,
            on_tool_call=lambda d: None
        )

    @patch.object(QueryExecutionService, '_gather_file_context', return_value='')
    @patch.object(QueryExecutionService, '_gather_image_content', return_value=([], []))
    def test_persists_system_prompt_tools_messages(self, mock_img, mock_fc, db):
        brain, session = self._setup(db)
        service = QueryExecutionService(db, MockEmbedder())
        service._llm = MagicMock()
        service._llm.stream = _fake_stream_no_tools

        ctx = QueryContext(session_id=session.id, brain=brain, query_text='hello')
        service.execute(ctx, self._callbacks())

        interaction_repo = InteractionRepository(db)
        interactions = interaction_repo.get_by_session(session.id)
        interaction = interactions[0]
        assert interaction.system_prompt is not None
        assert 'Livebrain' in interaction.system_prompt
        assert interaction.tools is not None
        assert isinstance(interaction.tools, list)
        assert interaction.messages is not None
        assert any(m['content'] == 'hello' for m in interaction.messages)

    @patch.object(QueryExecutionService, '_gather_file_context', return_value='')
    @patch.object(QueryExecutionService, '_gather_image_content', return_value=([], []))
    def test_persists_tool_call_records(self, mock_img, mock_fc, db):
        brain, session = self._setup(db)
        service = QueryExecutionService(db, MockEmbedder())
        service._llm = MagicMock()
        _fake_stream_with_tool_call._call_count = 0
        service._llm.stream = _fake_stream_with_tool_call

        ctx = QueryContext(session_id=session.id, brain=brain, query_text='search something')
        service.execute(ctx, self._callbacks())

        interaction_repo = InteractionRepository(db)
        tool_call_repo = ToolCallRepository(db)
        interactions = interaction_repo.get_by_session(session.id)
        interaction = interactions[0]
        records = tool_call_repo.get_by_interaction(interaction.id)
        assert len(records) == 1
        assert records[0].call_id == 'tc-1'
        assert records[0].tool_name == 'search_files'
        assert records[0].arguments == {'query': 'test'}
        assert records[0].duration_ms is not None
