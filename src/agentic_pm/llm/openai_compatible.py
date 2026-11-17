"""Local-first provider: any server speaking the OpenAI-compatible chat API.

Works with Ollama (`http://localhost:11434/v1`), vLLM, llama.cpp server and
LM Studio. No vendor SDK, just HTTP.
"""

from __future__ import annotations

from typing import Any

import httpx

from agentic_pm.llm.base import ChatMessage, Completion, LLMError


class OpenAICompatibleProvider:
    name = "openai-compatible"

    def __init__(
        self,
        model: str,
        base_url: str = "http://localhost:11434/v1",
        api_key: str | None = None,
        timeout: float = 120.0,
        reasoning_effort: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.model = model
        # For reasoning models (e.g. qwen3.x): "none" | "low" | "medium" | "high".
        # Short structured-output calls usually want "none" so thinking does not
        # consume the token budget before any answer is produced.
        self.reasoning_effort = reasoning_effort
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"), headers=headers, timeout=timeout, transport=transport
        )

    async def complete(
        self,
        messages: list[ChatMessage],
        *,
        json_schema: dict[str, Any] | None = None,
        max_tokens: int = 2048,
    ) -> Completion:
        body: dict[str, Any] = {
            "model": self.model,
            "messages": [m.model_dump() for m in messages],
            "max_tokens": max_tokens,
            "stream": False,
        }
        if self.reasoning_effort is not None:
            body["reasoning_effort"] = self.reasoning_effort
        if json_schema is not None:
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "result", "schema": json_schema, "strict": True},
            }
        try:
            resp = await self._client.post("/chat/completions", json=body)
        except httpx.HTTPError as e:
            raise LLMError(
                f"can't reach the model server at {self._client.base_url} "
                f"({e.__class__.__name__}). Is it running? For Ollama: `ollama serve`"
            ) from e
        if resp.status_code == 404:
            raise LLMError(await self._not_found())
        try:
            resp.raise_for_status()
        except httpx.HTTPError as e:
            raise LLMError(f"{self.name} request failed: {e}") from e
        data = resp.json()
        try:
            choice = data["choices"][0]
            text = choice["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as e:
            raise LLMError(f"unexpected response shape: {data!r:.300}") from e
        finish_reason = choice.get("finish_reason")
        if not text and finish_reason == "length":
            raise LLMError(
                f"no answer within max_tokens={max_tokens}; the model likely spent the budget "
                "on reasoning. Raise max_tokens or set reasoning_effort='none'."
            )
        usage = data.get("usage") or {}
        return Completion(
            text=text,
            model=data.get("model", self.model),
            finish_reason=finish_reason,
            input_tokens=usage.get("prompt_tokens"),
            output_tokens=usage.get("completion_tokens"),
        )

    async def _not_found(self) -> str:
        """A 404 almost always means the model isn't installed: say which ones are."""
        try:
            listed = (await self._client.get("/models")).json().get("data", [])
            names = sorted(str(m.get("id")) for m in listed if m.get("id"))
        except (httpx.HTTPError, ValueError, AttributeError):
            names = []
        hint = f" Available: {', '.join(names)}." if names else ""
        return (
            f"model '{self.model}' isn't available on {self._client.base_url}.{hint} "
            f"Set llm.model in team.yaml, or install it (Ollama: `ollama pull {self.model}`)."
        )

    async def aclose(self) -> None:
        await self._client.aclose()
