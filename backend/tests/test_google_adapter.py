import pytest
from agents.adapters.google_adapter import GoogleDirectAdapter
from agents.adapters.types import ModelExecutionError, ErrorCode

@pytest.mark.asyncio
async def test_google_empty_output_rejected():
    class MockModels:
        async def generate_content_stream(self, *args, **kwargs):
            async def _stream():
                if False: yield None
            return _stream()
            
    class MockAio:
        def __init__(self):
            self.models = MockModels()
            
    class MockClient:
        def __init__(self):
            self.aio = MockAio()
                    
    adapter = GoogleDirectAdapter(MockClient())
    with pytest.raises(ModelExecutionError) as exc:
        async for chunk in adapter.stream("model", "prompt", attempt_id="1"):
            pass
    assert exc.value.category == ErrorCode.PROVIDER_PROTOCOL_ERROR
    assert "Stream finished without yielding any content" in str(exc.value)
