import hashlib
import json
import os
import shutil
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from models import (
    Brain, Session, Resource, ResourceType, IndexStatus,
    FileReference, ToolCallDetail, QueryType
)
from services.database import (
    BrainRepository, SessionRepository, ResourceRepository,
    InteractionRepository, AIResponseRepository, ToolCallRepository,
    RAGService
)
from services.query_execution import QueryExecutionService, QueryContext, ExecutionCallbacks
from services.tools import REGISTRY, ToolContext
from services.scanner import FileScanner
from services.llm.interfaces import LLMResponse, ToolCall


FIXTURES_DIR = os.path.join(os.path.dirname(__file__), 'fixtures', 'sample_docs')


class MockEmbedder:
    def embed(self, text, is_query=True):
        h = hashlib.md5(text.encode()).digest()
        base = [b / 255.0 for b in h]
        return (base * 48)[:768]


def _make_stream(calls):
    it = iter(calls)
    def stream(*args, **kwargs):
        yield ''
        return next(it)
    return stream


def _tool_response(call_id, name, arguments):
    output_item = MagicMock()
    output_item.model_dump.return_value = {'type': 'function_call', 'name': name}
    return LLMResponse(
        text='', model='test', tokens_input=5, tokens_output=3,
        tool_calls=[ToolCall(call_id=call_id, name=name, arguments=json.dumps(arguments))],
        output_items=[output_item]
    )


def _text_response(text):
    return LLMResponse(text=text, model='test', tokens_input=8, tokens_output=4)


class TestE2EToolCalling:
    def _setup_brain_with_folder(self, db):
        brain = BrainRepository(db).create(Brain(name='Test Brain'))
        session = SessionRepository(db).create(Session(name='Test Session'))

        tmp_dir = tempfile.mkdtemp()
        for name in os.listdir(FIXTURES_DIR):
            shutil.copy(os.path.join(FIXTURES_DIR, name), os.path.join(tmp_dir, name))

        resource = ResourceRepository(db).create(Resource(
            resource_type=ResourceType.FOLDER,
            name='sample_docs',
            path=tmp_dir,
            index_status=IndexStatus.INDEXED
        ))
        ResourceRepository(db).link_to_brain(resource.id, brain.id)

        rag = RAGService(db)
        scanner = FileScanner()
        embedder = MockEmbedder()
        for filepath in scanner.scan_directory(tmp_dir):
            segments = scanner.extract_text_with_meta(filepath)
            rag.index_text_with_meta(
                resource.id, filepath, segments,
                lambda text: embedder.embed(text, is_query=False)
            )

        return brain, session, tmp_dir

    def _callbacks(self):
        data = {'steps': [], 'deltas': [], 'tool_calls': [], 'responses': []}
        return ExecutionCallbacks(
            on_step=lambda s: data['steps'].append(s),
            on_delta=lambda d: data['deltas'].append(d),
            on_complete=lambda r: data['responses'].append(r),
            on_tool_call=lambda d: data['tool_calls'].append(d)
        ), data

    @patch.object(QueryExecutionService, '_gather_file_context', return_value='')
    @patch.object(QueryExecutionService, '_gather_image_content', return_value=([], []))
    def test_search_files_e2e(self, _, __, db):
        brain, session, tmp_dir = self._setup_brain_with_folder(db)
        callbacks, data = self._callbacks()

        service = QueryExecutionService(db, MockEmbedder())
        service._llm = MagicMock()
        service._llm.stream = _make_stream([
            _tool_response('tc-1', 'search_files', {'query': 'revenue last quarter'}),
            _text_response('The revenue was $4.2M according to [the report](quarterly_report.txt)'),
        ])

        ctx = QueryContext(session_id=session.id, brain=brain, query_text='What was the revenue last quarter?')
        response = service.execute(ctx, callbacks)

        interaction = InteractionRepository(db).get_by_session(session.id)[0]
        records = ToolCallRepository(db).get_by_interaction(interaction.id)
        assert len(records) == 1
        assert records[0].tool_name == 'search_files'

        assert any(ref.display_name == 'quarterly_report.txt' for ref in response.file_references)
        assert '[the report](quarterly_report.txt)' in response.text

        assert any('Searched' in tc.summary for tc in data['tool_calls'])
        assert any(t.get('name') == 'search_files' for t in interaction.tools)

        shutil.rmtree(tmp_dir)

    @patch.object(QueryExecutionService, '_gather_file_context', return_value='')
    @patch.object(QueryExecutionService, '_gather_image_content', return_value=([], []))
    def test_read_file_e2e(self, _, __, db):
        brain, session, tmp_dir = self._setup_brain_with_folder(db)
        callbacks, data = self._callbacks()
        target_path = os.path.join(tmp_dir, 'meeting_notes.txt')

        service = QueryExecutionService(db, MockEmbedder())
        service._llm = MagicMock()
        service._llm.stream = _make_stream([
            _tool_response('tc-1', 'read_file', {'path': target_path}),
            _text_response('The meeting had four attendees.'),
        ])

        ctx = QueryContext(session_id=session.id, brain=brain, query_text='Who attended the meeting?')
        service.execute(ctx, callbacks)

        interaction = InteractionRepository(db).get_by_session(session.id)[0]
        records = ToolCallRepository(db).get_by_interaction(interaction.id)
        assert len(records) == 1
        assert records[0].tool_name == 'read_file'
        assert 'Sarah Chen' in records[0].result

        shutil.rmtree(tmp_dir)

    @patch.object(QueryExecutionService, '_gather_file_context', return_value='')
    @patch.object(QueryExecutionService, '_gather_image_content', return_value=([], []))
    def test_search_then_read_e2e(self, _, __, db):
        brain, session, tmp_dir = self._setup_brain_with_folder(db)
        callbacks, data = self._callbacks()
        target_path = os.path.join(tmp_dir, 'quarterly_report.txt')

        service = QueryExecutionService(db, MockEmbedder())
        service._llm = MagicMock()
        service._llm.stream = _make_stream([
            _tool_response('tc-1', 'search_files', {'query': 'revenue'}),
            _tool_response('tc-2', 'read_file', {'path': target_path}),
            _text_response('Revenue was $4.2M.'),
        ])

        ctx = QueryContext(session_id=session.id, brain=brain, query_text='Full revenue details?')
        service.execute(ctx, callbacks)

        interaction = InteractionRepository(db).get_by_session(session.id)[0]
        records = ToolCallRepository(db).get_by_interaction(interaction.id)
        assert len(records) == 2
        assert records[0].tool_name == 'search_files'
        assert records[1].tool_name == 'read_file'

        shutil.rmtree(tmp_dir)

    @patch.object(QueryExecutionService, '_gather_file_context', return_value='')
    @patch.object(QueryExecutionService, '_gather_image_content', return_value=([], []))
    def test_no_tools_without_folders(self, _, __, db):
        brain = BrainRepository(db).create(Brain(name='Empty Brain'))
        session = SessionRepository(db).create(Session(name='Session'))
        callbacks, data = self._callbacks()

        service = QueryExecutionService(db, MockEmbedder())
        service._llm = MagicMock()
        service._llm.stream = _make_stream([_text_response('Just a direct answer.')])

        ctx = QueryContext(session_id=session.id, brain=brain, query_text='Hello')
        service.execute(ctx, callbacks)

        interaction = InteractionRepository(db).get_by_session(session.id)[0]
        assert not any(t.get('name') == 'search_files' for t in interaction.tools)
        assert 'Search' not in interaction.system_prompt

    @patch.object(QueryExecutionService, '_gather_file_context', return_value='')
    @patch.object(QueryExecutionService, '_gather_image_content', return_value=([], []))
    def test_file_tree_in_prompt(self, _, __, db):
        brain, session, tmp_dir = self._setup_brain_with_folder(db)
        callbacks, data = self._callbacks()

        service = QueryExecutionService(db, MockEmbedder())
        service._llm = MagicMock()
        service._llm.stream = _make_stream([_text_response('Here is the answer.')])

        ctx = QueryContext(session_id=session.id, brain=brain, query_text='What files do you see?')
        service.execute(ctx, callbacks)

        interaction = InteractionRepository(db).get_by_session(session.id)[0]
        assert 'Available files' in interaction.system_prompt
        assert 'quarterly_report.txt' in interaction.system_prompt
        assert 'meeting_notes.txt' in interaction.system_prompt
        assert 'technical_spec.py' in interaction.system_prompt
        assert 'project_plan.md' in interaction.system_prompt

        shutil.rmtree(tmp_dir)
