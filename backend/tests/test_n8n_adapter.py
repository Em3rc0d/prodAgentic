import pytest
import httpx
from agents.adapters.n8n_adapter import N8nAdapter
from agents.adapters.types import ErrorCode, ModelExecutionError
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_n8n_adapter_model_mismatch():
    adapter = N8nAdapter("http://mock-n8n")
    
    # Create an AsyncMock for post
    mock_post = AsyncMock()
    from unittest.mock import MagicMock
    mock_response = MagicMock()
    mock_response.json.return_value = {"actual_model": "different-model", "text": "hello"}
    mock_post.return_value = mock_response

    with patch("httpx.AsyncClient.post", new=mock_post):
        with pytest.raises(ModelExecutionError) as exc:
            await adapter.generate("expected-model", "prompt")
            
        assert exc.value.code == ErrorCode.MODEL_MISMATCH
        assert exc.value.fallback_allowed is True
