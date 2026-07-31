import pytest
from agents.adapters.n8n_adapter import N8nAdapter
from agents.adapters.types import ModelExecutionError, ErrorCode

@pytest.mark.asyncio
async def test_n8n_adapter_validates_schema_and_identity(mocker):
    adapter = N8nAdapter("http://fake.url")
    
    async def mock_stream(*args, **kwargs):
        # Invalid schema version
        yield 'data: {"schema_version": "0.9", "chunk": "test"}\n\n'
        
    class MockResponse:
        @property
        def status_code(self): return 200
        def raise_for_status(self): pass
        async def aiter_lines(self):
            async for chunk in mock_stream():
                yield chunk
                
    class MockContext:
        async def __aenter__(self): return MockResponse()
        async def __aexit__(self, exc_type, exc_val, exc_tb): pass
        
    mocker.patch("httpx.AsyncClient.stream", return_value=MockContext())
    
    with pytest.raises(ModelExecutionError) as exc:
        async for chunk_type, chunk_data in adapter.stream("model", "prompt", attempt_id="1"):
            pass
            
    assert exc.value.category == ErrorCode.PROVIDER_PROTOCOL_ERROR
    assert "Invalid schema_version" in str(exc.value)
