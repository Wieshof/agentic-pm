"""Signal transport via signal-cli-rest-api (https://github.com/bbernhard/signal-cli-rest-api).

Environment: AGENT_PM_SIGNAL_API_URL (http://localhost:8080) and
AGENT_PM_SIGNAL_NUMBER (the agent's registered number, +43…). Run the
container in `normal` or `native` mode; `json-rpc` mode has no REST receive.

Signal is end-to-end encrypted; signal-cli holds the keys on your machine.
Receiving takes messages off Signal's queue, so nothing is kept here.
Voice notes are fetched into memory and their stored copy in signal-cli is
deleted right after the message was handled.
"""

from __future__ import annotations

import contextlib
from typing import Any
from urllib.parse import quote

import httpx

from agentic_pm.chat.base import ChatEvent


class SignalError(RuntimeError):
    pass


def _norm(number: str) -> str:
    return number.replace(" ", "")


class SignalTransport:
    name = "signal"

    def __init__(
        self, api_url: str, number: str, *, transport: httpx.AsyncBaseTransport | None = None
    ) -> None:
        if not (api_url and number):
            raise SignalError("Signal needs AGENT_PM_SIGNAL_API_URL and AGENT_PM_SIGNAL_NUMBER")
        self.number = _norm(number)
        self._client = httpx.AsyncClient(
            base_url=api_url.rstrip("/"), timeout=30.0, transport=transport
        )

    @classmethod
    def from_env(cls, env: dict[str, str]) -> SignalTransport:
        return cls(env.get("AGENT_PM_SIGNAL_API_URL", ""), env.get("AGENT_PM_SIGNAL_NUMBER", ""))

    async def _call(self, method: str, path: str, json_body: Any = None) -> httpx.Response:
        try:
            r = await self._client.request(method, path, json=json_body)
        except httpx.HTTPError as e:
            raise SignalError(f"Signal request failed: {e}") from e
        if r.status_code >= 400:
            raise SignalError(f"Signal {method} {path.split('?')[0]}: HTTP {r.status_code}")
        return r

    async def receive(self) -> list[ChatEvent]:
        r = await self._call("GET", f"/v1/receive/{quote(self.number)}?timeout=1")
        events: list[ChatEvent] = []
        for item in r.json() or []:
            env = item.get("envelope", item)
            data = env.get("dataMessage")
            sender = env.get("sourceNumber") or env.get("source") or ""
            if not data or not sender or _norm(sender) == self.number:
                continue  # receipts, typing notices, sync messages, own messages
            if data.get("groupInfo"):
                continue  # direct chats only
            quote_ = data.get("quote") or {}
            quoted_by = _norm(quote_.get("authorNumber") or quote_.get("author") or "")
            audio = [
                a["id"]
                for a in data.get("attachments") or []
                if str(a.get("contentType", "")).startswith("audio/") and a.get("id")
            ]
            events.append(
                ChatEvent(
                    platform=self.name,
                    sender=_norm(sender),
                    room=_norm(sender),
                    event_id=str(data.get("timestamp") or env.get("timestamp") or ""),
                    text=str(data.get("message") or ""),
                    reply_to_text=quote_.get("text") if quoted_by == self.number else None,
                    audio=audio,
                )
            )
        return events

    async def fetch_audio(self, event: ChatEvent, audio_id: str) -> bytes:
        r = await self._call("GET", f"/v1/attachments/{quote(audio_id, safe='')}")
        return r.content

    async def ack(self, event: ChatEvent) -> None:
        for audio_id in event.audio:  # signal-cli stores attachments on disk; remove them
            with contextlib.suppress(SignalError):
                await self._call("DELETE", f"/v1/attachments/{quote(audio_id, safe='')}")

    async def send(self, to: str, text: str) -> None:
        await self._call(
            "POST",
            "/v2/send",
            {"message": text, "number": self.number, "recipients": [_norm(to)]},
        )

    async def reply(self, event: ChatEvent, text: str) -> None:
        await self.send(event.room, text)

    async def aclose(self) -> None:
        await self._client.aclose()
