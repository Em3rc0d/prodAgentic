"""Request-local deadline inherited by independent provider stages."""
import asyncio
from contextvars import ContextVar

production_deadline: ContextVar[float | None] = ContextVar("production_deadline", default=None)


def stage_deadline(seconds: float) -> float:
    deadline = asyncio.get_running_loop().time() + seconds
    parent = production_deadline.get()
    return min(deadline, parent) if parent is not None else deadline
