import json
import os
import struct
import tempfile
import zlib

import pytest

from models import (
    Brain, Question, Session, TranscriptEntry, Interaction, AIResponse, ExecutionStep,
    FileReference, Resource, ResourceType, IndexStatus,
    QueryType, StepType, StepStatus, SpeakerType
)
from services.database import (
    BrainRepository, QuestionRepository, SessionRepository,
    TranscriptEntryRepository, InteractionRepository, ResourceRepository
)
from services.query_execution import QueryExecutionService, QueryContext, ExecutionCallbacks
from services.conversation import ConversationContext


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

        service = QueryExecutionService(db, MockEmbedder())
        result, refs, res_ids = service._tool_search_files('test', [resource.id])
        parsed = json.loads(result)
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
        assert 'LiveBrain' in prompt

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
        assert 'Directory structure' in prompt
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
            query='revenue growth',
            results_count=5,
            matched_files=['report.pdf', 'notes.txt'],
            duration_ms=42
        )
        assert detail.query == 'revenue growth'
        assert detail.results_count == 5
        assert len(detail.matched_files) == 2
        assert detail.duration_ms == 42

    def test_defaults(self):
        from models import ToolCallDetail
        detail = ToolCallDetail()
        assert detail.matched_files == []
        assert detail.duration_ms == 0


class TestToolExecution:
    def test_build_tools_with_folders(self, db):
        service = QueryExecutionService(db, MockEmbedder())
        tools = service._build_tools(['folder-1', 'folder-2'])
        names = [t.get('name') for t in tools if t.get('name')]
        assert 'search_files' in names
        assert any(t['type'] == 'web_search' for t in tools)

    def test_build_tools_without_folders(self, db):
        service = QueryExecutionService(db, MockEmbedder())
        tools = service._build_tools([])
        names = [t.get('name') for t in tools if t.get('name')]
        assert 'search_files' not in names
        assert any(t['type'] == 'web_search' for t in tools)

    def test_execute_tool_search_files(self, db):
        service = QueryExecutionService(db, MockEmbedder())
        result, refs, res_ids = service._tool_search_files('test query', [])
        assert isinstance(result, str)
        assert isinstance(refs, list)
        assert isinstance(res_ids, list)

    def test_execute_tool_unknown(self, db):
        service = QueryExecutionService(db, MockEmbedder())
        with pytest.raises(ValueError, match='Unknown tool'):
            service._execute_tool('nonexistent_tool', {}, [])

    def test_build_messages_simplified(self, db):
        service = QueryExecutionService(db, MockEmbedder())
        conv = ConversationContext(session_id='s1', brain_id='b1')
        messages = service._build_messages(conv, 'hello')
        assert messages[-1].content == 'hello'
        assert messages[-1].role == 'user'
