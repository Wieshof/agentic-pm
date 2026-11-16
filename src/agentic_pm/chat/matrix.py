"""Matrix transport (client-server API over httpx, no SDK).

Environment: AGENT_PM_MATRIX_HOMESERVER (https://matrix.example.org),
AGENT_PM_MATRIX_USER (@agent-pm:example.org), AGENT_PM_MATRIX_TOKEN.

Stateless like the IMAP inbox: what has been handled is the agent's own
read marker (`m.fully_read`) on the homeserver. On the very first start the
agent marks everything as read instead of answering old history.

Encryption: this transport speaks plain HTTP to the homeserver and can't
decrypt end-to-end encrypted rooms. Use unencrypted direct chats with the
agent, or run it behind Pantalaimon (an E2EE proxy). Encrypted messages get
a friendly note instead of being ignored silently.
"""

from __future__ import annotations

import json
import re
import secrets
from typing import Any
from urllib.parse import quote

import httpx

from agentic_pm.chat.base import ChatEvent

_FILTER = json.dumps(
    {
        "presence": {"types": []},
        "account_data": {"types": []},
        "room": {
            "timeline": {"limit": 50, "types": ["m.room.message", "m.room.encrypted"]},
            "state": {"types": []},
            "ephemeral": {"types": []},
            "account_data": {"types": ["m.fully_read"]},
        },
    }
)


_MXC = re.compile(r"^mxc://[A-Za-z0-9.:-]+/[A-Za-z0-9_-]+$")


class MatrixError(RuntimeError):
    pass


def _q(value: str) -> str:
    return quote(value, safe="")


def strip_reply_fallback(body: str) -> str:
    """Drop the legacy '> <@bot:x> quoted text' block some clients put on top."""
    lines = body.splitlines()
    if not lines or not lines[0].startswith("> "):
        return body
    i = 0
    while i < len(lines) and lines[i].startswith(">"):
        i += 1
    return "\n".join(lines[i:]).strip()


class MatrixTransport:
    name = "matrix"

    def __init__(
        self,
        homeserver: str,
        user_id: str,
        token: str,
        *,
        allowed_senders: set[str] | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if not (homeserver and user_id and token):
            raise MatrixError(
                "Matrix needs AGENT_PM_MATRIX_HOMESERVER, AGENT_PM_MATRIX_USER and "
                "AGENT_PM_MATRIX_TOKEN"
            )
        self.user_id = user_id
        # Only invites from these people are accepted (team.yaml channels.matrix).
        self.allowed = {s.lower() for s in allowed_senders or set()}
        self._client = httpx.AsyncClient(
            base_url=homeserver.rstrip("/"),
            headers={"Authorization": f"Bearer {token}"},
            timeout=40.0,
            transport=transport,
        )
        self._since: str | None = None
        self._dm: dict[str, str] = {}  # user id -> room id (cache; truth is m.direct)

    @classmethod
    def from_env(cls, env: dict[str, str], allowed: set[str]) -> MatrixTransport:
        return cls(
            env.get("AGENT_PM_MATRIX_HOMESERVER", ""),
            env.get("AGENT_PM_MATRIX_USER", ""),
            env.get("AGENT_PM_MATRIX_TOKEN", ""),
            allowed_senders=allowed,
        )

    async def _call(
        self, method: str, path: str, *, json_body: Any = None, params: Any = None
    ) -> Any:
        try:
            r = await self._client.request(method, path, json=json_body, params=params)
        except httpx.HTTPError as e:
            raise MatrixError(f"Matrix request failed: {e}") from e
        if r.status_code >= 400:
            raise MatrixError(f"Matrix {method} {path.split('?')[0]}: HTTP {r.status_code}")
        return r.json() if r.content else {}

    # ---------------------------------------------------------------- receive

    async def receive(self) -> list[ChatEvent]:
        first = self._since is None
        params: dict[str, Any] = {"filter": _FILTER, "timeout": 0}
        if self._since:
            params["since"] = self._since
        data = await self._call("GET", "/_matrix/client/v3/sync", params=params)
        self._since = data.get("next_batch")
        rooms = data.get("rooms", {})

        for room_id, room in rooms.get("invite", {}).items():
            await self._maybe_join(room_id, room)

        events: list[ChatEvent] = []
        for room_id, room in rooms.get("join", {}).items():
            timeline = [e for e in room.get("timeline", {}).get("events", []) if "event_id" in e]
            if first:
                marker = next(
                    (
                        e["content"].get("event_id")
                        for e in room.get("account_data", {}).get("events", [])
                        if e.get("type") == "m.fully_read"
                    ),
                    None,
                )
                ids = [e["event_id"] for e in timeline]
                if marker is None:  # never ran here: don't answer old history
                    if ids:
                        await self._mark_read(room_id, ids[-1])
                    continue
                if marker in ids:
                    timeline = timeline[ids.index(marker) + 1 :]
            for e in timeline:
                if e.get("sender") == self.user_id:
                    continue
                evt = await self._to_event(room_id, e)
                if evt is not None:
                    events.append(evt)
        return events

    async def _maybe_join(self, room_id: str, room: dict[str, Any]) -> None:
        inviter = next(
            (
                e.get("sender", "")
                for e in room.get("invite_state", {}).get("events", [])
                if e.get("type") == "m.room.member" and e.get("state_key") == self.user_id
            ),
            "",
        )
        if inviter.lower() in self.allowed:
            await self._call("POST", f"/_matrix/client/v3/join/{_q(room_id)}", json_body={})
            self._dm.setdefault(inviter, room_id)

    async def _to_event(self, room_id: str, e: dict[str, Any]) -> ChatEvent | None:
        base = {
            "platform": self.name,
            "sender": e.get("sender", ""),
            "room": room_id,
            "event_id": e["event_id"],
        }
        if e.get("type") == "m.room.encrypted":
            return ChatEvent(**base, encrypted=True)
        content = e.get("content", {})
        msgtype = content.get("msgtype")
        if content.get("m.new_content") or msgtype not in ("m.text", "m.audio"):
            return None  # edits, images, notices: nothing to do
        reply_to = None
        parent = content.get("m.relates_to", {}).get("m.in_reply_to", {}).get("event_id")
        if parent:
            reply_to = await self._own_message_text(room_id, parent)
        if msgtype == "m.audio":
            url = content.get("url", "")
            return ChatEvent(**base, reply_to_text=reply_to, audio=[url] if url else [])
        return ChatEvent(
            **base,
            text=strip_reply_fallback(str(content.get("body", ""))),
            reply_to_text=reply_to,
        )

    async def _own_message_text(self, room_id: str, event_id: str) -> str | None:
        """Text of the replied-to event, only if the agent itself sent it."""
        try:
            e = await self._call(
                "GET", f"/_matrix/client/v3/rooms/{_q(room_id)}/event/{_q(event_id)}"
            )
        except MatrixError:
            return None
        if e.get("sender") != self.user_id:
            return None
        return str(e.get("content", {}).get("body", ""))

    async def fetch_audio(self, event: ChatEvent, audio_id: str) -> bytes:
        if not _MXC.match(audio_id):  # comes from the message: never build odd paths
            raise MatrixError("not a Matrix media url")
        server_media = audio_id.removeprefix("mxc://")
        for path in (
            f"/_matrix/client/v1/media/download/{server_media}",  # authenticated media
            f"/_matrix/media/v3/download/{server_media}",  # older homeservers
        ):
            try:
                r = await self._client.get(path)
            except httpx.HTTPError as e:
                raise MatrixError(f"Matrix media download failed: {e}") from e
            if r.status_code < 400:
                return r.content
        raise MatrixError("Matrix media download failed")

    async def _mark_read(self, room_id: str, event_id: str) -> None:
        await self._call(
            "POST",
            f"/_matrix/client/v3/rooms/{_q(room_id)}/read_markers",
            json_body={"m.fully_read": event_id, "m.read": event_id},
        )

    async def ack(self, event: ChatEvent) -> None:
        await self._mark_read(event.room, event.event_id)

    # ------------------------------------------------------------------ send

    async def _send_room(self, room_id: str, text: str) -> None:
        txn = secrets.token_hex(8)
        await self._call(
            "PUT",
            f"/_matrix/client/v3/rooms/{_q(room_id)}/send/m.room.message/{txn}",
            json_body={"msgtype": "m.text", "body": text},
        )

    async def _dm_room(self, user: str) -> str:
        if user in self._dm:
            return self._dm[user]
        direct_path = f"/_matrix/client/v3/user/{_q(self.user_id)}/account_data/m.direct"
        try:
            direct = await self._call("GET", direct_path)
        except MatrixError:
            direct = {}
        joined = set(
            (await self._call("GET", "/_matrix/client/v3/joined_rooms")).get("joined_rooms", [])
        )
        room = next((r for r in direct.get(user, []) if r in joined), None)
        if room is None:
            created = await self._call(
                "POST",
                "/_matrix/client/v3/createRoom",
                json_body={"is_direct": True, "invite": [user], "preset": "trusted_private_chat"},
            )
            room = str(created["room_id"])
            direct.setdefault(user, []).append(room)
            await self._call("PUT", direct_path, json_body=direct)
        self._dm[user] = room
        return room

    async def send(self, to: str, text: str) -> None:
        await self._send_room(await self._dm_room(to), text)

    async def reply(self, event: ChatEvent, text: str) -> None:
        await self._send_room(event.room, text)

    async def aclose(self) -> None:
        await self._client.aclose()
