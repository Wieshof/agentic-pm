"""Speech-to-text for voice notes, locally. Audio and transcripts stay in RAM.

Two engines (team.yaml `speech.engine`):

* ``faster-whisper``: in-process, `uv sync --extra voice` (or `pip install
  agentic-pm[voice]`). The model is loaded on first use and kept in memory.
* ``whisper-cpp``: a whisper.cpp server you run yourself (`speech.url`,
  e.g. http://localhost:8080/inference). Audio goes over HTTP to it, so keep
  it on localhost or your own network.

Nothing is written to disk by this module.
"""

from __future__ import annotations

import asyncio
import io
from typing import Any, Protocol

import httpx

from agentic_pm.config.team import Speech


class SpeechError(RuntimeError):
    pass


class Transcriber(Protocol):
    async def transcribe(self, audio: bytes, language: str | None = None) -> str: ...


class FasterWhisper:
    def __init__(self, model: str = "small") -> None:
        self.model_name = model
        self._model: Any = None

    def _load(self) -> Any:
        if self._model is None:
            try:
                from faster_whisper import WhisperModel  # type: ignore[import-not-found]
            except ImportError as e:
                raise SpeechError(
                    "faster-whisper isn't installed: run `uv sync --extra voice`"
                ) from e
            self._model = WhisperModel(self.model_name, device="auto", compute_type="int8")
        return self._model

    def _run(self, audio: bytes, language: str | None) -> str:
        segments, _ = self._load().transcribe(io.BytesIO(audio), language=language)
        return " ".join(s.text.strip() for s in segments).strip()

    async def transcribe(self, audio: bytes, language: str | None = None) -> str:
        return await asyncio.to_thread(self._run, audio, language)


class WhisperCppServer:
    def __init__(self, url: str, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.url = url
        self._transport = transport

    async def transcribe(self, audio: bytes, language: str | None = None) -> str:
        data = {"response_format": "json", "temperature": "0"}
        if language:
            data["language"] = language
        try:
            async with httpx.AsyncClient(timeout=120.0, transport=self._transport) as client:
                r = await client.post(
                    self.url,
                    data=data,
                    files={"file": ("voice", audio, "application/octet-stream")},
                )
        except httpx.HTTPError as e:
            raise SpeechError(f"whisper.cpp server not reachable: {e}") from e
        if r.status_code >= 400:
            raise SpeechError(f"whisper.cpp server: HTTP {r.status_code}")
        return str(r.json().get("text", "")).strip()


def transcriber_from_settings(s: Speech) -> Transcriber | None:
    if s.engine == "faster-whisper":
        return FasterWhisper(s.model)
    if s.engine == "whisper-cpp":
        if not s.url:
            raise SpeechError("speech.url is required for engine whisper-cpp")
        return WhisperCppServer(s.url)
    return None
