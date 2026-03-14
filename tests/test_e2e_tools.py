import json
import os
import shutil

import keyring
import pytest

from models import (
    Brain, Session, Resource, ResourceType, IndexStatus,
    StepType, StepStatus
)
from services.database import (
    BrainRepository, SessionRepository, ResourceRepository,
    InteractionRepository, AIResponseRepository, ToolCallRepository,
    RAGService
)
from services.embedder import Embedder
from services.scanner import FileScanner
from services.query_execution import QueryExecutionService, QueryContext, ExecutionCallbacks
from ui.markdown_renderer import render_markdown


FIXTURES_DIR = os.path.join(os.path.dirname(__file__), 'fixtures', 'sample_docs')

HAS_API_KEY = bool(keyring.get_password('Livebrain', 'openai_api_key'))
HAS_MODEL = os.path.isfile(
    os.path.join(Embedder.get_model_dir(), 'onnx', 'model_q4.onnx')
)

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skipif(not HAS_API_KEY, reason='No OpenAI API key in keychain'),
    pytest.mark.skipif(not HAS_MODEL, reason='No ONNX embedding model on disk'),
]


@pytest.fixture
def embedder():
    return Embedder()


@pytest.fixture
def indexed_brain(db, embedder, tmp_path):
    for name in os.listdir(FIXTURES_DIR):
        shutil.copy(os.path.join(FIXTURES_DIR, name), tmp_path / name)

    brain = BrainRepository(db).create(Brain(name='Research Assistant'))
    session = SessionRepository(db).create(Session(name='E2E Test'))
    resource = ResourceRepository(db).create(Resource(
        resource_type=ResourceType.FOLDER,
        name='sample_docs',
        path=str(tmp_path),
        index_status=IndexStatus.INDEXED
    ))
    ResourceRepository(db).link_to_brain(resource.id, brain.id)

    rag = RAGService(db)
    scanner = FileScanner()
    for filepath in scanner.scan_directory(str(tmp_path)):
        segments = scanner.extract_text_with_meta(filepath)
        rag.index_text_with_meta(
            resource.id, filepath, segments,
            lambda text: embedder.embed(text, is_query=False)
        )

    return brain, session, resource


def test_full_tool_calling_pipeline(db, embedder, indexed_brain, qapp):
    brain, session, resource = indexed_brain

    steps, deltas, tool_calls = [], [], []
    callbacks = ExecutionCallbacks(
        on_step=lambda s: steps.append(s),
        on_delta=lambda d: deltas.append(d),
        on_complete=lambda r: None,
        on_tool_call=lambda d: tool_calls.append(d)
    )

    service = QueryExecutionService(db, embedder)
    ctx = QueryContext(
        session_id=session.id,
        brain=brain,
        query_text='What was the Q3 2025 revenue and who is the tech lead for Project Phoenix?'
    )
    response = service.execute(ctx, callbacks)

    # --- 1. LLM produced a real response ---
    assert response.text
    assert len(deltas) > 0
    assert response.tokens_input > 0
    assert response.tokens_output > 0
    assert response.latency_ms > 0

    # --- 2. Tool calls happened ---
    assert len(tool_calls) > 0
    step_types = [s.step_type for s in steps if s.status == StepStatus.IN_PROGRESS]
    assert StepType.LISTENING in step_types
    assert StepType.GENERATING in step_types
    assert StepType.SEARCHING_FILES in step_types

    tc = tool_calls[0]
    assert tc.summary
    assert len(tc.details) > 0

    # --- 3. Tool call records persisted correctly ---
    interaction = InteractionRepository(db).get_by_session(session.id)[0]
    records = ToolCallRepository(db).get_by_interaction(interaction.id)
    assert len(records) >= 1
    rec = records[0]
    assert rec.call_id
    assert rec.tool_name == 'search_files'
    assert 'query' in rec.arguments
    parsed = json.loads(rec.result)
    assert isinstance(parsed, list)
    assert len(parsed) > 0
    assert rec.duration_ms >= 0

    # --- 4. File references are real paths ---
    assert len(response.file_references) > 0
    for ref in response.file_references:
        assert os.path.isabs(ref.filepath)
        assert os.path.exists(ref.filepath)
        assert ref.display_name
        assert isinstance(ref.relevance_score, float)

    # --- 5. Interaction trace has complete prompt/tools/messages ---
    assert 'Livebrain' in interaction.system_prompt
    assert brain.name in interaction.system_prompt
    assert 'speech recognition' in interaction.system_prompt
    assert 'Available files' in interaction.system_prompt
    assert 'quarterly_report.txt' in interaction.system_prompt

    tool_names = [t.get('name', t['type']) for t in interaction.tools]
    assert 'web_search' in tool_names
    assert 'search_files' in tool_names
    assert 'read_file' in tool_names

    assert any(
        'revenue' in str(m.get('content', '')).lower() or 'phoenix' in str(m.get('content', '')).lower()
        for m in interaction.messages
    )

    # --- 6. AI response persisted and matches ---
    persisted = AIResponseRepository(db).get_by_interaction(interaction.id)
    assert persisted.text == response.text
    assert persisted.model_used
    assert len(persisted.file_references) == len(response.file_references)

    # --- 7. LLM produced citation links and linkify converts to file:// URLs ---
    import re
    links = re.findall(r'\[([^\]]+)\]\(([^)]+)\)', response.text)
    assert len(links) > 0, f'LLM did not produce any markdown citation links in: {response.text}'

    from ui.widgets.chat_feed import AnswerItem
    item = AnswerItem()
    item._file_refs = response.file_references
    html = render_markdown(response.text)
    linkified = item._linkify_sources(html)

    ref_names = {ref.display_name for ref in response.file_references}
    linked_refs = [href for _, href in links if href in ref_names]
    assert len(linked_refs) > 0, f'LLM links {links} do not match any file refs {ref_names}'

    for href in linked_refs:
        ref = next(r for r in response.file_references if r.display_name == href)
        assert f'file://{ref.filepath}' in linkified
