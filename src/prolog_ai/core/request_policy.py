"""Scoped controls for a workflow; each physical HTTP attempt consumes its budget."""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RequestPolicy:
    before_attempt: Callable[[], None]
    on_usage: Callable[[dict[str, Any]], None] | None = None
    max_output_tokens: int = 32768
    prompt_cache_prefix: str | None = None


current_policy: ContextVar[RequestPolicy | None] = ContextVar("llm_request_policy", default=None)


@contextmanager
def request_policy(policy: RequestPolicy) -> Iterator[None]:
    if not 1 <= policy.max_output_tokens <= 128000:
        raise ValueError("Invalid output budget")
    token = current_policy.set(policy)
    try:
        yield
    finally:
        current_policy.reset(token)
