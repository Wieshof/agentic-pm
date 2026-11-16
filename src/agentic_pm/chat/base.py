"""What every chat transport (Matrix, Signal, later WhatsApp) provides."""

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel


class ChatEvent(BaseModel):
    """One incoming chat message, already reduced to what the agent needs."""

    platform: str  # "matrix" | "signal"
    sender: str  # @sam:example.org | +436601234567
    room: str  # where a reply goes (Matrix room id, or the sender for Signal)
    event_id: str
    text: str = ""
    # Text of the agent message this one replies to, only if the platform
    # confirms the agent wrote it (Matrix: fetched from the server; Signal:
    # quote author is the agent's number, and proposals are signed anyway).
    reply_to_text: str | None = None
    audio: list[str] = []  # platform ids of voice notes / audio attachments
    encrypted: bool = False  # Matrix E2EE event the agent can't read


class ChatTransport(Protocol):
    name: str

    async def receive(self) -> list[ChatEvent]:
        """New messages since the last call (state lives on the server)."""
        ...

    async def send(self, to: str, text: str) -> None:
        """Direct message to a person (Matrix user id or phone number)."""
        ...

    async def reply(self, event: ChatEvent, text: str) -> None:
        """Answer in the conversation `event` came from."""
        ...

    async def fetch_audio(self, event: ChatEvent, audio_id: str) -> bytes:
        """Download a voice note into memory (never to disk)."""
        ...

    async def ack(self, event: ChatEvent) -> None:
        """Mark `event` as handled (read marker / delete stored attachments)."""
        ...

    async def aclose(self) -> None: ...
