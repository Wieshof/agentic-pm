import json
import os

import httpx
import pytest

from agentic_pm.config.team import LLMSettings
from agentic_pm.llm import (
    ChatMessage,
    LLMError,
    LLMProvider,
    OpenAICompatibleProvider,
    provider_from_settings,
)

MSGS = [ChatMessage(role="user", content="hi")]


def make(handler: object) -> OpenAICompatibleProvider:
    return OpenAICompatibleProvider(
        model="m",
        base_url="http://llm.test/v1",
        transport=httpx.MockTransport(handler),  # type: ignore[arg-type]
    )


async def test_request_shape_and_parsing() -> None:
    seen: dict[str, object] = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["url"] = str(req.url)
        seen["body"] = json.loads(req.content)
        return httpx.Response(
            200,
            json={
                "model": "m",
                "choices": [{"message": {"role": "assistant", "content": "hello"}}],
                "usage": {"prompt_tokens": 3, "completion_tokens": 1},
            },
        )

    p = make(handler)
    out = await p.complete(MSGS, json_schema={"type": "object"})
    assert out.text == "hello" and out.output_tokens == 1
    assert seen["url"] == "http://llm.test/v1/chat/completions"
    body = seen["body"]
    assert isinstance(body, dict)
    assert body["response_format"]["type"] == "json_schema"


async def test_http_error_becomes_llm_error() -> None:
    p = make(lambda req: httpx.Response(500, text="boom"))
    with pytest.raises(LLMError):
        await p.complete(MSGS)


async def test_bad_shape_becomes_llm_error() -> None:
    p = make(lambda req: httpx.Response(200, json={"nope": 1}))
    with pytest.raises(LLMError, match="unexpected response"):
        await p.complete(MSGS)


async def test_reasoning_only_truncation_is_reported() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        assert json.loads(req.content)["reasoning_effort"] == "none"
        return httpx.Response(
            200,
            json={"choices": [{"finish_reason": "length", "message": {"content": ""}}]},
        )

    p = OpenAICompatibleProvider(
        model="m",
        base_url="http://llm.test/v1",
        reasoning_effort="none",
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(LLMError, match="reasoning"):
        await p.complete(MSGS, max_tokens=50)


def test_factory_defaults_to_local() -> None:
    p = provider_from_settings(LLMSettings())
    assert isinstance(p, LLMProvider)
    assert p.name == "openai-compatible"
    with pytest.raises(ValueError):
        provider_from_settings(LLMSettings(provider="mystery"))


@pytest.mark.skipif(not os.environ.get("AGENT_PM_LIVE_LLM"), reason="set AGENT_PM_LIVE_LLM=model")
async def test_live_local_model() -> None:
    p = OpenAICompatibleProvider(model=os.environ["AGENT_PM_LIVE_LLM"], reasoning_effort="none")
    out = await p.complete(
        [ChatMessage(role="user", content='Reply with JSON {"ok": true}')],
        json_schema={
            "type": "object",
            "properties": {"ok": {"type": "boolean"}},
            "required": ["ok"],
            "additionalProperties": False,
        },
        max_tokens=50,
    )
    assert json.loads(out.text)["ok"] is True


async def test_missing_model_says_which_ones_exist() -> None:
    import httpx as _httpx

    from agentic_pm.llm import ChatMessage as _Msg
    from agentic_pm.llm.base import LLMError as _Err
    from agentic_pm.llm.openai_compatible import OpenAICompatibleProvider

    def handler(req: _httpx.Request) -> _httpx.Response:
        if req.url.path.endswith("/models"):
            return _httpx.Response(200, json={"data": [{"id": "qwen3.5:latest"}, {"id": "gemma4"}]})
        return _httpx.Response(404, json={"error": "model not found"})

    p = OpenAICompatibleProvider("llama3.1:8b", transport=_httpx.MockTransport(handler))
    try:
        await p.complete([_Msg(role="user", content="hi")])
    except _Err as e:
        assert "llama3.1:8b" in str(e) and "gemma4, qwen3.5:latest" in str(e)
        assert "ollama pull llama3.1:8b" in str(e)
    else:
        raise AssertionError("expected LLMError")
