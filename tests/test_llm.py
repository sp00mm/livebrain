from services.llm import Message, LLMResponse, LLMProvider, StreamCallback, LLMService, ToolCall
from services.llm.service import DEFAULT_MODEL


class TestMessage:
    def test_dataclass(self):
        msg = Message(role='user', content='hello')
        assert msg.role == 'user'
        assert msg.content == 'hello'

    def test_roles(self):
        for role in ['user', 'assistant', 'system']:
            msg = Message(role=role, content='test')
            assert msg.role == role


class TestLLMResponse:
    def test_dataclass(self):
        resp = LLMResponse(text='hello', model='gpt-4o')
        assert resp.text == 'hello'
        assert resp.model == 'gpt-4o'
        assert resp.tokens_input == 0
        assert resp.tokens_output == 0

    def test_with_tokens(self):
        resp = LLMResponse(text='test', model='gpt-4o', tokens_input=10, tokens_output=20)
        assert resp.tokens_input == 10
        assert resp.tokens_output == 20


class TestLLMProvider:
    def test_interface(self):
        assert hasattr(LLMProvider, 'complete')
        assert hasattr(LLMProvider, 'stream')
        assert hasattr(LLMProvider, 'is_available')


class TestStreamCallback:
    def test_type_exists(self):
        assert StreamCallback is not None


class TestLLMService:
    def test_init(self, db):
        service = LLMService(db)
        assert service.db == db

    def test_default_model(self):
        assert DEFAULT_MODEL == 'gpt-5-chat-latest'


class TestToolCall:
    def test_dataclass(self):
        tc = ToolCall(call_id='call_1', name='search_files', arguments='{"query": "test"}')
        assert tc.call_id == 'call_1'
        assert tc.name == 'search_files'
        assert tc.arguments == '{"query": "test"}'


class TestLLMResponseWithToolCalls:
    def test_empty_tool_calls(self):
        resp = LLMResponse(text='hello', model='gpt-4o')
        assert resp.tool_calls == []
        assert resp.output_items == []

    def test_with_tool_calls(self):
        tc = ToolCall(call_id='call_1', name='search_files', arguments='{}')
        resp = LLMResponse(text='', model='gpt-4o', tool_calls=[tc])
        assert len(resp.tool_calls) == 1
        assert resp.tool_calls[0].name == 'search_files'
