import json
import os
import shutil

import keyring
import pytest

from models import (
    Brain, Session, Resource, ResourceType, IndexStatus,
    FileReference, StepType, StepStatus
)
from services.database import (
    BrainRepository, SessionRepository, ResourceRepository,
    InteractionRepository, AIResponseRepository, ExecutionStepRepository,
    ToolCallRepository, RAGService
)
from services.embedder import Embedder
from services.scanner import FileScanner
from services.query_execution import QueryExecutionService, QueryContext, ExecutionCallbacks

pytestmark = pytest.mark.e2e

TESTDATA_DIR = os.path.join(os.path.dirname(__file__), 'testdata')

HAS_API_KEY = bool(keyring.get_password('LiveBrain', 'openai_api_key'))
HAS_MODEL = os.path.isfile(
    os.path.join(Embedder.get_model_dir(), 'onnx', 'model_q4.onnx')
)

requires_api_key = pytest.mark.skipif(
    not HAS_API_KEY, reason='No OpenAI API key in keychain'
)
requires_model = pytest.mark.skipif(
    not HAS_MODEL, reason='No ONNX embedding model on disk'
)


@pytest.fixture
def embedder():
    return Embedder()


@pytest.fixture
def test_folder(tmp_path):
    for name in ('quarterly_report.txt', 'meeting_notes.txt', 'product_spec.txt'):
        shutil.copy(os.path.join(TESTDATA_DIR, name), tmp_path / name)
    return tmp_path


@pytest.fixture
def indexed_brain(db, embedder, test_folder):
    brain = BrainRepository(db).create(Brain(name='Test Brain'))
    session = SessionRepository(db).create(Session(name='Test Session'))
    resource = ResourceRepository(db).create(Resource(
        resource_type=ResourceType.FOLDER,
        name='testdata',
        path=str(test_folder),
        index_status=IndexStatus.INDEXED
    ))
    ResourceRepository(db).link_to_brain(resource.id, brain.id)

    rag = RAGService(db)
    scanner = FileScanner()
    for filepath in scanner.scan_directory(str(test_folder)):
        segments = scanner.extract_text_with_meta(filepath)
        rag.index_text_with_meta(
            resource.id, filepath, segments,
            lambda text: embedder.embed(text, is_query=False)
        )

    return brain, session, resource


def _run_query(db, embedder, brain, session, query_text):
    steps, deltas, tool_calls = [], [], []
    callbacks = ExecutionCallbacks(
        on_step=lambda s: steps.append(s),
        on_delta=lambda d: deltas.append(d),
        on_complete=lambda r: None,
        on_tool_call=lambda d: tool_calls.append(d)
    )
    service = QueryExecutionService(db, embedder)
    ctx = QueryContext(session_id=session.id, brain=brain, query_text=query_text)
    return service.execute(ctx, callbacks), steps, deltas, tool_calls


@requires_api_key
@requires_model
def test_full_query_execution(db, embedder, indexed_brain):
    brain, session, _ = indexed_brain
    response, steps, deltas, _ = _run_query(
        db, embedder, brain, session,
        'What was Acme Corp Q3 revenue?'
    )
    assert response.text
    assert '4.2' in response.text
    assert len(deltas) > 0
    step_types = [s.step_type for s in steps if s.status == StepStatus.IN_PROGRESS]
    assert StepType.LISTENING in step_types
    assert StepType.GENERATING in step_types
    assert response.tokens_input > 0
    assert response.tokens_output > 0
    assert response.latency_ms > 0


@requires_api_key
@requires_model
def test_tool_calls_triggered(db, embedder, indexed_brain):
    brain, session, _ = indexed_brain
    _, steps, _, tool_calls = _run_query(
        db, embedder, brain, session,
        'What are the Widget Pro specs?'
    )
    assert len(tool_calls) > 0
    tc = tool_calls[0]
    assert tc.query
    assert tc.duration_ms >= 0
    step_types = [s.step_type for s in steps if s.status == StepStatus.IN_PROGRESS]
    assert StepType.SEARCHING_FILES in step_types


@requires_api_key
@requires_model
def test_interaction_trace_persisted(db, embedder, indexed_brain):
    brain, session, _ = indexed_brain
    _run_query(db, embedder, brain, session, 'Tell me about the team meeting')

    interactions = InteractionRepository(db).get_by_session(session.id)
    interaction = interactions[0]
    assert 'LiveBrain' in interaction.system_prompt
    assert brain.name in interaction.system_prompt
    assert 'speech recognition' in interaction.system_prompt
    tool_names = [t.get('name', t['type']) for t in interaction.tools]
    assert 'web_search' in tool_names
    assert 'search_files' in tool_names
    assert any('team meeting' in str(m.get('content', '')).lower() for m in interaction.messages)


@requires_api_key
@requires_model
def test_tool_call_records_persisted(db, embedder, indexed_brain):
    brain, session, _ = indexed_brain
    _run_query(db, embedder, brain, session, 'What is the Widget Pro battery life?')

    interactions = InteractionRepository(db).get_by_session(session.id)
    records = ToolCallRepository(db).get_by_interaction(interactions[0].id)
    assert len(records) >= 1
    rec = records[0]
    assert rec.call_id
    assert rec.tool_name == 'search_files'
    assert 'query' in rec.arguments
    parsed = json.loads(rec.result)
    assert isinstance(parsed, list)
    assert rec.duration_ms >= 0


@requires_api_key
@requires_model
def test_file_references_correct(db, embedder, indexed_brain):
    brain, session, _ = indexed_brain
    response, _, _, _ = _run_query(
        db, embedder, brain, session,
        'What is the Widget Pro price?'
    )
    assert len(response.file_references) > 0
    for ref in response.file_references:
        assert '/' not in ref.display_name
        assert ref.display_name.endswith('.txt')
        assert os.path.isabs(ref.filepath)
        assert os.path.exists(ref.filepath)
        assert isinstance(ref.relevance_score, float)


@requires_api_key
@requires_model
def test_ai_response_persisted(db, embedder, indexed_brain):
    brain, session, _ = indexed_brain
    response, _, _, _ = _run_query(
        db, embedder, brain, session,
        'How many employees does Acme have?'
    )

    interactions = InteractionRepository(db).get_by_session(session.id)
    persisted = AIResponseRepository(db).get_by_interaction(interactions[0].id)
    assert persisted.text == response.text
    assert persisted.model_used
    assert persisted.tokens_input > 0
    assert persisted.tokens_output > 0
    assert persisted.latency_ms > 0
    assert len(persisted.file_references) == len(response.file_references)


def test_linkify_sources_with_file_refs(qapp):
    from ui.widgets.chat_feed import AnswerItem
    item = AnswerItem()
    item._file_refs = [
        FileReference(
            resource_id='r1', filepath='/tmp/docs/report.txt',
            display_name='report.txt', relevance_score=0.9
        ),
        FileReference(
            resource_id='r2', filepath='/tmp/docs/notes.pdf',
            display_name='notes.pdf', relevance_score=0.8,
            source_meta={'page': 5}
        )
    ]

    html = '<a href="report.txt">see the report</a>'
    result = item._linkify_sources(html)
    assert 'file:///tmp/docs/report.txt' in result
    assert 'see the report' in result

    html_page = '<a href="notes.pdf">page ref</a>'
    result_page = item._linkify_sources(html_page)
    assert 'file:///tmp/docs/notes.pdf#page=5' in result_page

    html_unknown = '<a href="unknown.doc">other link</a>'
    result_unknown = item._linkify_sources(html_unknown)
    assert result_unknown == html_unknown


def test_linkify_sources_with_code_content(qapp):
    from ui.widgets.chat_feed import AnswerItem
    item = AnswerItem()
    item._file_refs = [
        FileReference(
            resource_id='r1', filepath='/tmp/docs/spec.txt',
            display_name='spec.txt', relevance_score=0.9
        )
    ]
    html = '<a href="spec.txt"><code>spec.txt</code></a>'
    result = item._linkify_sources(html)
    assert 'file:///tmp/docs/spec.txt' in result
    assert '<code>spec.txt</code>' in result


@requires_model
def test_real_embedder_produces_searchable_vectors(db, embedder, indexed_brain):
    brain, session, resource = indexed_brain
    embedding = embedder.embed('revenue profit', is_query=True)
    rag = RAGService(db)
    results = rag.search(embedding, resource_ids=[resource.id], limit=5)
    assert len(results) > 0
    top = results[0]
    assert 'quarterly_report' in top['chunk'].filepath
    assert 0 < top['similarity'] <= 1


@requires_api_key
@requires_model
def test_multiple_queries_share_conversation_context(db, embedder, indexed_brain):
    brain, session, _ = indexed_brain
    _run_query(db, embedder, brain, session, 'What was Q3 revenue?')
    _run_query(db, embedder, brain, session, 'And what about profit margin?')

    interactions = InteractionRepository(db).get_by_session(session.id)
    assert len(interactions) == 2
    assert len(interactions[1].messages) > len(interactions[0].messages)
