"""Provider-agnostic LLM interface (ADR-0001).

No module outside `agentic_pm.llm` may import a model vendor SDK.
"""

from __future__ import annotations

from typing import Any, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict


class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["system", "user", "assistant"]
    content: str


class Completion(BaseModel):
    text: str
    model: str
    finish_reason: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None


class LLMError(RuntimeError):
    pass


@runtime_checkable
class LLMProvider(Protocol):
    name: str

    async def complete(
        self,
        messages: list[ChatMessage],
        *,
        json_schema: dict[str, Any] | None = None,
        max_tokens: int = 2048,
    ) -> Completion:
        """Return a completion. With `json_schema`, the text must be JSON matching it."""
        ...
