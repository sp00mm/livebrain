import os

import keyring
import pytest

from models import FileReference
from services.database import RAGService
from services.embedder import Embedder

pytestmark = pytest.mark.e2e

HAS_MODEL = os.path.isfile(
    os.path.join(Embedder.get_model_dir(), 'onnx', 'model_q4.onnx')
)

requires_model = pytest.mark.skipif(
    not HAS_MODEL, reason='No ONNX embedding model on disk'
)


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
