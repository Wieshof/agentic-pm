"""Phase 3 chat: tags, short answers, transports, chat router, triangulation, chat briefs."""

import json
from datetime import UTC, date, datetime, timedelta
from typing import Any

import httpx
import pytest

from agentic_pm.actions import Guard
from agentic_pm.adapters import InMemoryTracker, Task, TaskRef, TaskStatus
from agentic_pm.adapters.base import Comment
from agentic_pm.approvals import Signer
from agentic_pm.chat import tags
from agentic_pm.chat.answers import parse_date, parse_estimate, yes_no
from agentic_pm.chat.base import ChatEvent
from agentic_pm.chat.inbound import ChatRouter, poll_chat
from agentic_pm.chat.matrix import MatrixError, MatrixTransport, strip_reply_fallback
from agentic_pm.chat.signal import SignalTransport
from agentic_pm.config.team import TeamConfig
from agentic_pm.email_routing import InboundMessage
from agentic_pm.engine.triangulation import comment_conflicts, conflict, detect_claim
from agentic_pm.inbound import Router
from agentic_pm.notify import ChatNotifier, MultiNotifier, RecordingNotifier
from agentic_pm.speech import WhisperCppServer, transcriber_from_settings

TODAY = date(2026, 11, 16)  # a Monday
REPO = "acme/app"
KEY = "k" * 32
BOT_MX = "@agent-pm:acme.test"
BOT_SIG = "+43660000000"


def cfg(**people: Any) -> TeamConfig:
    base = {
        "alex": {
            "role": "lead",
            "archetype": "reader",
            "channels": {"email": "alex@acme.test"},
        },
        "sam": {
            "role": "dev",
            "archetype": "writer",
            "language": "de",
            "channels": {"matrix": "@sam:acme.test", "signal": "+43 660 1111111"},
            "brief": {"format": "chat", "when": "08:30"},
        },
        "kim": {
            "role": "dev",
            "archetype": "writer",
            "channels": {"signal": "+43 660 2222222"},
        },
    }
    base.update(people)
    return TeamConfig.model_validate(
        {
            "project": {
                "tracker": "github",
                "repo": REPO,
                "leads": ["alex"],
                "agent_email": "pm@acme.test",
                "allow_writes": True,
                "control_plane_url": "https://pm.acme.test",
            },
            "people": base,
        }
    )


def ref(i: str = "12") -> TaskRef:
    return TaskRef(tracker="github", project=REPO, id=i)


def tracker(**kw: Any) -> InMemoryTracker:
    t = InMemoryTracker(
        [
            Task(
                ref=ref(),
                title="Fix auth timeout",
                status=kw.pop("status", TaskStatus.IN_PROGRESS),
                assignees=["sam"],
                url="https://x/12",
                **kw,
            )
        ]
    )
    t.name = "github"
    return t


class FakeChat:
    """In-memory transport: messages to receive, replies and sends recorded."""

    def __init__(self, name: str = "signal", events: list[ChatEvent] | None = None) -> None:
        self.name = name
        self.events = events or []
        self.replies: list[str] = []
        self.sent: list[tuple[str, str]] = []
        self.acked: list[str] = []
        self.audio = b"RIFF...fake"

    async def receive(self) -> list[ChatEvent]:
        out, self.events = self.events, []
        return out

    async def send(self, to: str, text: str) -> None:
        self.sent.append((to, text))

    async def reply(self, event: ChatEvent, text: str) -> None:
        self.replies.append(text)

    async def fetch_audio(self, event: ChatEvent, audio_id: str) -> bytes:
        return self.audio

    async def ack(self, event: ChatEvent) -> None:
        self.acked.append(event.event_id)

    async def aclose(self) -> None:
        pass


class FakeWhisper:
    def __init__(self, text: str) -> None:
        self.text = text
        self.calls: list[tuple[bytes, str | None]] = []

    async def transcribe(self, audio: bytes, language: str | None = None) -> str:
        self.calls.append((audio, language))
        return self.text


def setup(t: InMemoryTracker | None = None, transcriber: Any = None, signer: bool = True) -> Any:
    c = cfg()
    t = t or tracker()
    notifier = RecordingNotifier()
    guard = Guard(c, t, notifier, Signer(KEY) if signer else None)
    router = Router(c, guard, notifier)
    return c, t, notifier, ChatRouter(c, router, transcriber, today=lambda: TODAY)


def evt(text: str = "", sender: str = "+436601111111", **kw: Any) -> ChatEvent:
    return ChatEvent(
        platform=kw.pop("platform", "signal"),
        sender=sender,
        room=sender,
        event_id=kw.pop("event_id", "1"),
        text=text,
        **kw,
    )


# ------------------------------------------------------------------ tags


def test_tags_round_trip_and_signature() -> None:
    assert tags.parse("Hi\n\n— #12") == tags.Tag(id="12")
    assert tags.parse("Q?\n— #P-7 · due?") == tags.Tag(id="P-7", ask="due")
    p = tags.proposal(KEY, "12", "status", "done")
    parsed = tags.parse(f"Should I?\n\n{p.render()}")
    assert parsed == p
    assert tags.verified_patch(p, KEY) is not None
    assert tags.verified_patch(p, "other-key") is None  # forged with another key
    forged = p.model_copy(update={"value": "closed"})  # same sig, other value
    assert tags.verified_patch(forged, KEY) is None
    assert tags.verified_patch(p, None) is None
    assert tags.parse("nothing tagged here") is None


# --------------------------------------------------------------- answers


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("yes", True),
        ("Ja, passt 👍", True),
        ("ok", True),
        ("nein", False),
        ("no thanks", False),
        ("lieber nicht", False),
        ("ok but not today", None),
        ("It depends on the client and what they decide next week", None),
        ("", None),
    ],
)
def test_yes_no(text: str, expected: bool | None) -> None:
    assert yes_no(text) is expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Friday", date(2026, 11, 20)),
        ("bis Freitag", date(2026, 11, 20)),
        ("next Monday", date(2026, 11, 23)),
        ("morgen", date(2026, 11, 17)),
        ("25.11.", date(2026, 11, 25)),
        ("2.1.", date(2027, 1, 2)),  # in the past this year: next year
        ("25. November", date(2026, 11, 25)),
        ("Dec 3", date(2026, 12, 3)),
        ("2026-12-01", date(2026, 12, 1)),
        ("in 2 weeks", date(2026, 11, 30)),
        ("in 3 Tagen", date(2026, 11, 19)),
        ("31.02.", None),
        ("whenever the client says so", None),
    ],
)
def test_parse_date(text: str, expected: date | None) -> None:
    assert parse_date(text, TODAY) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("4h", 4.0),
        ("about 2 days", 16.0),
        ("1,5 Tage", 12.0),
        ("3 Stunden", 3.0),
        ("a week", None),
        ("1 week", 40.0),
        ("half a day", 4.0),
        ("no idea", None),
    ],
)
def test_parse_estimate(text: str, expected: float | None) -> None:
    assert parse_estimate(text) == expected


# --------------------------------------------------------- triangulation


@pytest.mark.parametrize(
    ("text", "kind"),
    [
        ("#12 is done, merged this morning.", "done"),
        ("Ist erledigt!", "done"),
        ("I'm stuck on the login part.", "blocked"),
        ("Ich warte auf das Logo vom Kunden.", "blocked"),
        ("Started on it today.", "started"),
        ("Not done yet.", None),
        ("Noch nicht fertig.", None),
        ("Is it done?", None),
        ("Almost finished.", None),
        ("I haven't finished it.", None),
        ("Let me know once it's merged.", None),
        ("Done with the API, but stuck on the UI.", None),  # contradictory
    ],
)
def test_detect_claim(text: str, kind: str | None) -> None:
    claim = detect_claim(text)
    assert (claim.kind if claim else None) == kind


def test_conflicts_only_when_tracker_disagrees() -> None:
    task = Task(ref=ref(), title="X", status=TaskStatus.IN_PROGRESS)
    done = detect_claim("done!")
    started = detect_claim("started")
    assert done and started
    c = conflict(task, done)
    assert c and c.proposed is TaskStatus.DONE
    assert conflict(task, started) is None  # already in progress
    assert conflict(task.model_copy(update={"status": TaskStatus.DONE}), done) is None


def test_comment_conflicts_latest_human_comment_of_the_last_day() -> None:
    now = datetime(2026, 11, 16, 9, tzinfo=UTC)

    def task(*comments: tuple[str, str, int]) -> Task:
        return Task(
            ref=ref(),
            title="X",
            status=TaskStatus.OPEN,
            comments=[
                Comment(author=a, body=b, created_at=now - timedelta(hours=h))
                for a, b, h in comments
            ],
        )

    [c] = comment_conflicts([task(("sam", "Fixed and deployed.", 2))], now)
    assert c.by == "sam" and c.proposed is TaskStatus.DONE
    assert comment_conflicts([task(("sam", "Fixed.", 30))], now) == []  # too old
    assert comment_conflicts([task(("sam", "Fixed.", 3), ("kim", "Not fixed yet", 1))], now) == []
    agent = "✅ done <!-- agent-pm-audit {} -->"
    assert comment_conflicts([task(("bot", agent, 1))], now) == []  # the agent's own


# ------------------------------------------------------------ transports


def test_strip_reply_fallback() -> None:
    body = "> <@agent-pm:acme.test> Should I?\n> — #12\n\nyes"
    assert strip_reply_fallback(body) == "yes"
    assert strip_reply_fallback("plain") == "plain"


async def test_matrix_first_sync_without_marker_skips_history() -> None:
    calls: list[tuple[str, str]] = []

    def handler(req: httpx.Request) -> httpx.Response:
        calls.append((req.method, req.url.path))
        if req.url.path.endswith("/sync"):
            return httpx.Response(
                200,
                json={
                    "next_batch": "s1",
                    "rooms": {
                        "join": {
                            "!r:acme.test": {
                                "timeline": {
                                    "events": [
                                        {
                                            "type": "m.room.message",
                                            "event_id": "$old",
                                            "sender": "@sam:acme.test",
                                            "content": {"msgtype": "m.text", "body": "old"},
                                        }
                                    ]
                                }
                            }
                        }
                    },
                },
            )
        return httpx.Response(200, json={})

    mx = MatrixTransport(
        "https://mx.acme.test", BOT_MX, "tok", transport=httpx.MockTransport(handler)
    )
    assert await mx.receive() == []
    assert ("POST", "/_matrix/client/v3/rooms/!r:acme.test/read_markers") in calls


async def test_matrix_events_after_marker_reply_context_audio_and_invites() -> None:
    joined: list[str] = []

    def handler(req: httpx.Request) -> httpx.Response:
        path = req.url.path
        if path.endswith("/sync"):
            msg = {"type": "m.room.message", "sender": "@sam:acme.test"}
            return httpx.Response(
                200,
                json={
                    "next_batch": "s1",
                    "rooms": {
                        "invite": {
                            "!dm:acme.test": {
                                "invite_state": {
                                    "events": [
                                        {
                                            "type": "m.room.member",
                                            "state_key": BOT_MX,
                                            "sender": "@sam:acme.test",
                                        }
                                    ]
                                }
                            },
                            "!spam:evil.test": {
                                "invite_state": {
                                    "events": [
                                        {
                                            "type": "m.room.member",
                                            "state_key": BOT_MX,
                                            "sender": "@mallory:evil.test",
                                        }
                                    ]
                                }
                            },
                        },
                        "join": {
                            "!r:acme.test": {
                                "account_data": {
                                    "events": [
                                        {"type": "m.fully_read", "content": {"event_id": "$a"}}
                                    ]
                                },
                                "timeline": {
                                    "events": [
                                        {
                                            **msg,
                                            "event_id": "$a",
                                            "content": {"msgtype": "m.text", "body": "seen"},
                                        },
                                        {
                                            **msg,
                                            "event_id": "$b",
                                            "content": {
                                                "msgtype": "m.text",
                                                "body": "> <@agent-pm:acme.test> Q\n\nja",
                                                "m.relates_to": {
                                                    "m.in_reply_to": {"event_id": "$bot"}
                                                },
                                            },
                                        },
                                        {
                                            **msg,
                                            "event_id": "$c",
                                            "content": {
                                                "msgtype": "m.audio",
                                                "body": "voice",
                                                "url": "mxc://acme.test/abc",
                                            },
                                        },
                                        {
                                            "type": "m.room.encrypted",
                                            "sender": "@sam:acme.test",
                                            "event_id": "$d",
                                            "content": {},
                                        },
                                    ]
                                },
                            }
                        },
                    },
                },
            )
        if path.endswith("/event/$bot"):
            return httpx.Response(
                200, json={"sender": BOT_MX, "content": {"body": "Should I?\n— #12"}}
            )
        if "/join/" in path:
            joined.append(path)
            return httpx.Response(200, json={"room_id": "!dm:acme.test"})
        if "/media/download/acme.test/abc" in path:
            return httpx.Response(200, content=b"OGG")
        return httpx.Response(404, json={})

    mx = MatrixTransport(
        "https://mx.acme.test",
        BOT_MX,
        "tok",
        allowed_senders={"@sam:acme.test"},
        transport=httpx.MockTransport(handler),
    )
    events = await mx.receive()
    assert [e.event_id for e in events] == ["$b", "$c", "$d"]  # after the read marker
    assert events[0].text == "ja" and events[0].reply_to_text == "Should I?\n— #12"
    assert events[1].audio == ["mxc://acme.test/abc"]
    assert await mx.fetch_audio(events[1], "mxc://acme.test/abc") == b"OGG"
    assert events[2].encrypted
    assert joined == ["/_matrix/client/v3/join/!dm:acme.test"]  # not the stranger's room


async def test_matrix_media_url_must_be_well_formed() -> None:
    mx = MatrixTransport(
        "https://mx", BOT_MX, "tok", transport=httpx.MockTransport(lambda r: httpx.Response(200))
    )
    e = evt(platform="matrix")
    for bad in ("mxc://acme.test/../../client/v3/sync", "https://evil.test/x", "mxc://a/b?c=d"):
        with pytest.raises(MatrixError):
            await mx.fetch_audio(e, bad)


async def test_matrix_reply_to_someone_elses_message_has_no_context() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"sender": "@mallory:evil.test", "content": {"body": "x"}})

    mx = MatrixTransport("https://mx", BOT_MX, "tok", transport=httpx.MockTransport(handler))
    assert await mx._own_message_text("!r", "$e") is None


async def test_matrix_send_creates_direct_room_once() -> None:
    seen: list[tuple[str, str, Any]] = []

    def handler(req: httpx.Request) -> httpx.Response:
        body = json.loads(req.content) if req.content else None
        seen.append((req.method, req.url.path, body))
        if req.url.path.endswith("/account_data/m.direct") and req.method == "GET":
            return httpx.Response(404, json={})
        if req.url.path.endswith("/joined_rooms"):
            return httpx.Response(200, json={"joined_rooms": []})
        if req.url.path.endswith("/createRoom"):
            return httpx.Response(200, json={"room_id": "!new:acme.test"})
        return httpx.Response(200, json={})

    mx = MatrixTransport("https://mx", BOT_MX, "tok", transport=httpx.MockTransport(handler))
    await mx.send("@sam:acme.test", "hi")
    await mx.send("@sam:acme.test", "again")
    creates = [s for s in seen if s[1].endswith("/createRoom")]
    assert len(creates) == 1 and creates[0][2]["invite"] == ["@sam:acme.test"]
    sends = [s for s in seen if "/send/m.room.message/" in s[1]]
    assert [s[2]["body"] for s in sends] == ["hi", "again"]
    assert all("!new:acme.test" in s[1] for s in sends)


async def test_signal_receive_send_and_attachment_cleanup() -> None:
    seen: list[tuple[str, str, Any]] = []

    def handler(req: httpx.Request) -> httpx.Response:
        body = json.loads(req.content) if req.content else None
        seen.append((req.method, req.url.path, body))
        if req.url.path.startswith("/v1/receive/"):
            return httpx.Response(
                200,
                json=[
                    {
                        "envelope": {
                            "sourceNumber": "+436601111111",
                            "dataMessage": {
                                "timestamp": 111,
                                "message": "ja",
                                "quote": {"authorNumber": BOT_SIG, "text": "Q?\n— #12"},
                            },
                        }
                    },
                    {
                        "envelope": {
                            "sourceNumber": "+436602222222",
                            "dataMessage": {
                                "timestamp": 222,
                                "message": "fake",
                                "quote": {"authorNumber": "+436609999999", "text": "— #12"},
                                "attachments": [{"id": "att1", "contentType": "audio/aac"}],
                            },
                        }
                    },
                    {"envelope": {"sourceNumber": "+436601111111", "receiptMessage": {}}},
                    {
                        "envelope": {
                            "sourceNumber": "+436601111111",
                            "dataMessage": {"message": "group", "groupInfo": {"groupId": "g"}},
                        }
                    },
                ],
            )
        if req.url.path == "/v1/attachments/att1" and req.method == "GET":
            return httpx.Response(200, content=b"AAC")
        return httpx.Response(201, json={})

    sig = SignalTransport("http://signal:8080", BOT_SIG, transport=httpx.MockTransport(handler))
    events = await sig.receive()
    assert [e.event_id for e in events] == ["111", "222"]
    assert events[0].reply_to_text == "Q?\n— #12"
    assert events[1].reply_to_text is None  # quoted someone else
    assert events[1].audio == ["att1"]
    assert await sig.fetch_audio(events[1], "att1") == b"AAC"
    await sig.ack(events[1])
    assert ("DELETE", "/v1/attachments/att1", None) in seen
    await sig.send("+43 660 1111111", "hi")
    assert seen[-1] == (
        "POST",
        "/v2/send",
        {"message": "hi", "number": BOT_SIG, "recipients": ["+436601111111"]},
    )


async def test_whisper_cpp_server() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        assert b'name="language"' in req.content and b"de" in req.content
        return httpx.Response(200, json={"text": " Ist erledigt. "})

    w = WhisperCppServer("http://localhost:8080/inference", httpx.MockTransport(handler))
    assert await w.transcribe(b"OGG", language="de") == "Ist erledigt."
    assert transcriber_from_settings(cfg().speech) is None  # off by default


# -------------------------------------------------------------- notifier


def test_reach_order_and_handle_for_chat() -> None:
    c = cfg()
    assert c.reach_order("sam") == ["signal", "matrix"]
    assert c.reach_order("alex") == ["email"]
    assert c.handle_for_chat("signal", "+436601111111") == "sam"
    assert c.handle_for_chat("matrix", "@SAM:acme.test") == "sam"
    assert c.handle_for_chat("signal", "+430000") is None
    prefer = cfg(sam={**c.people["sam"].model_dump(exclude_none=True), "prefer": ["matrix"]})
    assert prefer.reach_order("sam") == ["matrix", "signal"]


async def test_multi_notifier_order_and_reply_channel() -> None:
    c = cfg()
    sig, mx = FakeChat("signal"), FakeChat("matrix")
    n = MultiNotifier(c, {"signal": ChatNotifier(c, sig), "matrix": ChatNotifier(c, mx)})
    assert await n.notify("sam", "Hi", "text", ref=ref())
    assert sig.sent == [("+43 660 1111111", "Hi\n\ntext\n\n— #12")] and mx.sent == []
    assert await n.notify("sam", "", "reply", channel="matrix")
    assert mx.sent == [("@sam:acme.test", "reply")]
    assert not await n.notify("alex", "x", "y")  # email isn't wired here


# ----------------------------------------------------------- chat router


async def test_unknown_sender_and_encrypted() -> None:
    _, _, _, chat = setup()
    t = FakeChat()
    assert await chat.handle(t, evt("hi", sender="+430000000")) == "ignored_unknown_sender"
    assert t.replies == []
    assert await chat.handle(t, evt(encrypted=True)) == "encrypted"
    assert "verschlüsselte" in t.replies[0]  # Sam is German


async def test_free_text_with_task_number_becomes_a_note() -> None:
    _, tr, notifier, chat = setup()
    out = await chat.handle(FakeChat(), evt("Kurzes Update zu #12: Review läuft."))
    assert out == "note"
    task = await tr.get_task(ref())
    assert "Review läuft" in task.comments[-1].body and "Signal" in task.comments[-1].body
    assert notifier.sent[-1].channel == "signal"  # the thank-you goes back via Signal


async def test_without_task_asks_which_one() -> None:
    _, _, notifier, chat = setup()
    assert await chat.handle(FakeChat(), evt("Kurzes Update")) == "asked_for_task"
    assert "#142" in notifier.sent[-1].text and "Mail" not in notifier.sent[-1].text


async def test_voice_note_is_transcribed_in_memory() -> None:
    whisper = FakeWhisper("Update zu #12: Review läuft.")
    _, tr, _, chat = setup(transcriber=whisper)
    t = FakeChat()
    assert await chat.handle(t, evt(audio=["att1"])) == "note"
    assert whisper.calls == [(b"RIFF...fake", "de")]
    assert "(voice note)" in (await tr.get_task(ref())).comments[-1].body

    _, _, _, off = setup()
    assert await off.handle(t, evt(audio=["att1"])) == "voice_off"
    assert "Sprachnachricht" in t.replies[-1]


async def test_owner_claim_in_chat_is_confirmed_with_yes() -> None:
    _, tr, notifier, chat = setup()
    t = FakeChat()
    out = await chat.handle(t, evt("#12 ist erledigt, alles gemergt."))
    assert out == "note+status_confirm_asked"
    question = notifier.sent[-1]
    assert question.channel == "signal" and "Soll ich es auf erledigt setzen?" in question.text
    tag = tags.parse(question.text)
    assert tag and tag.field == "status" and tag.value == "done"

    out = await chat.handle(t, evt("ja", reply_to_text=question.text, event_id="2"))
    assert out == "confirm_applied" and "Erledigt ✅" in t.replies[-1]
    task = await tr.get_task(ref())
    assert task.status is TaskStatus.DONE
    assert '"actor": "sam"' in task.comments[-1].body or task.status is TaskStatus.DONE


async def test_no_and_forged_proposals_change_nothing() -> None:
    _, tr, _, chat = setup()
    t = FakeChat()
    real = tags.proposal(KEY, "12", "status", "done").render()
    assert await chat.handle(t, evt("nein", reply_to_text=real)) == "confirm_declined"
    forged = tags.Tag(id="12", field="status", value="done", sig="0" * 10).render()
    assert await chat.handle(t, evt("ja", reply_to_text=forged)) == "confirm_unverified"
    assert (await tr.get_task(ref())).status is TaskStatus.IN_PROGRESS


async def test_non_owner_yes_becomes_an_approval_request() -> None:
    _, tr, notifier, chat = setup()
    real = tags.proposal(KEY, "12", "status", "done").render()
    kim = evt("yes", sender="+436602222222", reply_to_text=real)
    assert await chat.handle(FakeChat(), kim) == "confirm_pending"
    assert (await tr.get_task(ref())).status is TaskStatus.IN_PROGRESS
    assert any(s.handle == "sam" and "/approve?t=" in s.text for s in notifier.sent)


async def test_non_owner_claim_asks_the_owner() -> None:
    _, tr, notifier, chat = setup()
    out = await chat.handle(FakeChat(), evt("#12 is done!", sender="+436602222222"))
    assert out == "note+status_check_requested"
    assert any(s.handle == "sam" and "/approve?t=" in s.text for s in notifier.sent)
    assert "asked Sam" in notifier.sent[-1].text
    assert (await tr.get_task(ref())).status is TaskStatus.IN_PROGRESS


async def test_email_claim_never_counts_as_owner_confirmation() -> None:
    _c, tr, _notifier, chat = setup()
    msg = InboundMessage(
        sender="sam@acme.test",
        handle="sam",
        ref=ref(),
        subject="Re: #12",
        text="It's done.",
        message_id=None,
    )
    assert await chat.router.handle(msg) == "note+status_check_requested"
    assert (await tr.get_task(ref())).status is TaskStatus.IN_PROGRESS  # forged mail is harmless


async def test_due_answer_round_trip() -> None:
    _, tr, _, chat = setup(tracker())
    t = FakeChat()
    out = await chat.handle(t, evt("Freitag", reply_to_text="Kein Termin?\n\n— #12 · due?"))
    assert out == "due_confirm_asked"
    assert "Fr., 20.11.2026" in t.replies[-1]
    out = await chat.handle(t, evt("ja", reply_to_text=t.replies[-1], event_id="2"))
    assert out == "confirm_applied"
    assert (await tr.get_task(ref())).due == date(2026, 11, 20)


async def test_answer_to_a_bundled_question_names_the_task() -> None:
    _, _tr, _, chat = setup()
    t = FakeChat()
    assert await chat.handle(t, evt("#12 Freitag")) == "due_confirm_asked"
    assert await chat.handle(t, evt("#12 2 Tage")) == "estimate_confirm_asked"
    # a real sentence with a date is a note, not an answer
    out = await chat.handle(t, evt("#12 the client meeting moved to Friday, we'll see after"))
    assert out == "note"


async def test_unreadable_answer_is_kept_as_a_note() -> None:
    _, tr, _, chat = setup()
    out = await chat.handle(
        FakeChat(), evt("hängt vom Kunden ab", reply_to_text="Termin?\n\n— #12 · due?")
    )
    assert out == "note"
    assert "Kunden" in (await tr.get_task(ref())).comments[-1].body


async def test_without_signing_key_nothing_is_proposed() -> None:
    _, _tr, _, chat = setup(signer=False)
    assert await chat.handle(FakeChat(), evt("#12 ist erledigt.")) == "note"
    out = await chat.handle(FakeChat(), evt("Freitag", reply_to_text="— #12 · due?"))
    assert out == "note"


async def test_poll_acks_every_message_even_on_failure() -> None:
    _, _, _, chat = setup()

    class Boom(FakeChat):
        async def reply(self, event: ChatEvent, text: str) -> None:
            raise RuntimeError("network")

    t = Boom(events=[evt(encrypted=True, event_id="a"), evt("hi", sender="+43000", event_id="b")])
    assert await poll_chat(t, chat) == ["failed", "ignored_unknown_sender"]
    assert t.acked == ["a", "b"]


# ------------------------------------------------------------ chat brief


async def test_chat_brief_sends_gaps_and_conflicts_as_single_questions() -> None:
    from agentic_pm.runtime import build_runtime

    now = datetime.now(UTC)
    t = InMemoryTracker(
        [
            Task(ref=ref("12"), title="No date", status=TaskStatus.OPEN, assignees=["sam"]),
            Task(
                ref=ref("13"),
                title="Logo",
                status=TaskStatus.IN_PROGRESS,
                assignees=["sam"],
                due=TODAY + timedelta(days=3),
                comments=[Comment(author="kim", body="Logo is done.", created_at=now)],
            ),
        ]
    )
    t.name = "github"
    rt = build_runtime(cfg(), t, env={"AGENT_PM_SIGNING_KEY": KEY}, dry_run=True, use_llm=False)
    assert rt.brief_handles("08:30") == ["sam"]
    assert await rt.briefs(["sam"]) == 1
    sent = rt.notifier.sent  # type: ignore[attr-defined]
    assert all(s.channel == "signal" for s in sent)
    texts = [s.text for s in sent]
    # #12 isn't urgent (nothing waits on it, no date soon): bundled into the brief
    assert "🧩" in texts[0] and "Bis wann soll es fertig sein?" in texts[0]
    assert "🔍" not in texts[0]  # the conflict comes as its own question
    assert "Kim" in texts[1] and "Soll ich es auf erledigt setzen?" in texts[1]
    tag = tags.parse(texts[1])
    assert tag and tags.verified_patch(tag, KEY) is not None
    assert len(texts) == 2
