import pytest
from agents.router import CircuitBreaker, CircuitState

def test_circuit_breaker_half_open_logic():
    cb = CircuitBreaker()
    cb.record_failure("test", ttl_seconds=-1)
    
    # First allowed probe
    assert cb.is_allowed() is True
    assert cb.state == CircuitState.HALF_OPEN
    assert cb._half_open_probe_active is True
    
    # Second probe rejected concurrently
    assert cb.is_allowed() is False
    
    # Success resets state
    cb.record_success()
    assert cb.state == CircuitState.CLOSED
    assert cb.is_allowed() is True
    assert cb._half_open_probe_active is False
