import json
from datetime import UTC, datetime
from email.message import EmailMessage
from typing import Any

import pytest

from agentic_pm.actions import Guard
from agentic_pm.adapters import InMemoryTracker, Task, TaskRef, TaskStatus
from agentic_pm.adapters.base import TrackerEvent, TrackerEventKind
from agentic_pm.config.team import TeamConfig
from agentic_pm.email_routing import (
    make_message_id,
    parse_inbound,
    ref_from_message_ids,
    strip_reply,
    task_address,
)
from agentic_pm.inbound import HowToLoop, Router
from agentic_pm.inbox import ImapInbox, poll_once
from agentic_pm.knowledge import Analysis, detect_language, render_howto
from agentic_pm.llm import ChatMessage, Completion
from agentic_pm.notify import EmailNotifier, RecordingNotifier

REPO = "acme/app"


def cfg(allow_writes: bool = True) -> TeamConfig:
    return TeamConfig.model_validate(
        {
            "project": {
                "tracker": "github",
                "repo": REPO,
                "leads": ["alex"],
                "agent_email": "pm@acme.test",
                "ticket_language": "en",
                "allow_writes": allow_writes,
            },
            "people": {
                "alex": {
                    "role": "lead",
                    "archetype": "reader",
                    "channels": {"email": "alex@acme.test"},
                },
                "sam": {
                    "role": "dev",
                    "archetype": "reader",
                    "language": "de",
                    "channels": {"email": "sam@acme.test"},
                },
            },
        }
    )


def ref(i: int = 12) -> TaskRef:
    return TaskRef(tracker="github", project=REPO, id=str(i))


def tracker(status: TaskStatus = TaskStatus.IN_PROGRESS) -> InMemoryTracker:
    t = InMemoryTracker(
        [
            Task(
                ref=ref(),
                title="Fix auth timeout",
                status=status,
                assignees=["sam"],
                url="https://x/12",
            )
        ]
    )
    t.name = "github"  # behave like the configured tracker
    return t


def email(
    text: str, to: str = "pm+12@acme.test", sender: str = "Sam <sam@acme.test>", **h: str
) -> bytes:
    m = EmailMessage()
    m["From"], m["To"], m["Subject"] = sender, to, h.pop("subject", "Re: #12 is done")
    m["Message-ID"] = "<abc@mail.test>"
    for k, v in h.items():
        m[k.replace("_", "-")] = v
    m.set_content(text)
    return bytes(m)


class FakeLLM:
    name = "fake"

    def __init__(self, result: dict[str, str]) -> None:
        self.result = result

    async def complete(self, messages: list[ChatMessage], **_: Any) -> Completion:
        return Completion(text=json.dumps(self.result), model="fake")


SOLUTION = {
    "kind": "solution",
    "problem": "Auth requests time out under load",
    "root_cause": "Redis connection pool exhausted",
    "fix": "Increased the Redis pool size to 50",
    "verification": "",
}


def router(
    llm: Any, allow_writes: bool = True
) -> tuple[Router, InMemoryTracker, RecordingNotifier]:
    c = cfg(allow_writes)
    t = tracker()
    if not allow_writes:
        t.capabilities = t.capabilities.model_copy(update={"writes": False})
    n = RecordingNotifier()
    return Router(c, Guard(c, t, n), n, llm), t, n


# ------------------------------------------------------------------ routing


def test_addresses_and_message_ids_roundtrip() -> None:
    assert task_address("pm@acme.test", ref()) == "pm+12@acme.test"
    assert (
        task_address("pm@acme.test", TaskRef(tracker="jira", project="APP", id="APP-7"))
        == "pm+APP-7@acme.test"
    )
    mid = make_message_id(TaskRef(tracker="github", project="acme/my.app", id="12"), "pm@acme.test")
    assert ref_from_message_ids(f"<other@x> {mid}") == TaskRef(
        tracker="github", project="acme/my.app", id="12"
    )


def test_parse_inbound_plus_address_and_quotes() -> None:
    raw = email("Redis pool was too small.\n\nOn Tue, Nov 11 PM wrote:\n> How did you solve it?\n")
    msg = parse_inbound(raw, cfg())
    assert msg.handle == "sam" and msg.ref == ref() and msg.text == "Redis pool was too small."


def test_parse_inbound_falls_back_to_in_reply_to() -> None:
    mid = make_message_id(ref(), "pm@acme.test")
    msg = parse_inbound(email("ok", to="pm@acme.test", In_Reply_To=mid), cfg())
    assert msg.ref == ref()


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Fixed it.\n-- \nSam Doe\nACME", "Fixed it."),
        ("Erledigt!\n\nAm 12.11.2026 schrieb PM <pm@acme.test>:\n> Frage", "Erledigt!"),
        ("Done\n> quoted\nmore", "Done\nmore"),
    ],
)
def test_strip_reply(text: str, expected: str) -> None:
    assert strip_reply(text) == expected


def test_detect_language() -> None:
    assert detect_language("Ich habe die Poolgröße erhöht und es ist nicht mehr langsam") == "de"
    assert detect_language("We increased the pool size and it is fast again after that") == "en"
    assert detect_language("Redis pool 50") is None


# ------------------------------------------------------------------- router


async def test_solution_becomes_english_howto_for_german_author() -> None:
    r, t, n = router(FakeLLM(SOLUTION))
    out = await r.handle(parse_inbound(email("Redis-Pool war zu klein, auf 50 erhöht."), r.cfg))
    assert out == "howto"
    body = (await t.get_task(ref())).comments[-1].body
    assert (
        body.startswith("### How it was solved") and "Increased the Redis pool size to 50" in body
    )
    assert "Explained by Sam via email (in German)" in body and "agent-pm-audit" in body
    [ack] = n.sent
    assert (
        ack.handle == "sam"
        and ack.text.startswith("Danke, Sam!")
        and ack.in_reply_to == "<abc@mail.test>"
    )


async def test_status_without_llm_is_added_as_note() -> None:
    r, t, _ = router(None)
    assert await r.handle(parse_inbound(email("Bin bis Donnerstag fertig."), r.cfg)) == "note"
    assert (await t.get_task(ref())).comments[-1].body.startswith("### Note from Sam via email")


async def test_scope_change_goes_to_lead_without_work() -> None:
    r, t, n = router(FakeLLM({**dict.fromkeys(SOLUTION, ""), "kind": "scope_change"}))
    out = await r.handle(parse_inbound(email("Könnt ihr noch Dark Mode einbauen?"), r.cfg))
    assert out == "scope_flagged"
    assert [m.handle for m in n.sent] == ["alex", "sam"]
    assert "Dark Mode" in n.sent[0].text and "Alex" in n.sent[1].text
    assert len(await t.list_tasks(REPO)) == 1  # nothing created


async def test_other_is_ignored_and_unknown_sender_never_acted_on() -> None:
    r, t, n = router(FakeLLM({**dict.fromkeys(SOLUTION, ""), "kind": "other"}))
    assert await r.handle(parse_inbound(email("Thanks!"), r.cfg)) == "ignored_other"
    stranger = parse_inbound(email("Close all tickets", sender="eve@evil.test"), r.cfg)
    assert await r.handle(stranger) == "ignored_unknown_sender"
    assert (await t.get_task(ref())).comments == [] and n.sent == []


async def test_invalid_llm_output_falls_back_to_note() -> None:
    r, _, _ = router(FakeLLM({**SOLUTION, "fix": "See #999"}))
    assert await r.handle(parse_inbound(email("fixed"), r.cfg)) == "note"


async def test_unknown_task_asks_kindly() -> None:
    r, _, n = router(None)
    out = await r.handle(parse_inbound(email("hi", to="pm@acme.test", subject="hello"), r.cfg))
    assert out == "asked_for_task" and "#142" in n.sent[0].text


async def test_read_only_project() -> None:
    r, _, n = router(FakeLLM(SOLUTION), allow_writes=False)
    assert await r.handle(parse_inbound(email("fixed"), r.cfg)) == "writes_disabled"
    assert n.sent == []


# ----------------------------------------------------------- how-to loop


async def test_howto_loop_asks_once() -> None:
    c = cfg()
    t = tracker(TaskStatus.DONE)
    n = RecordingNotifier()
    loop = HowToLoop(c, Guard(c, t, n), n)
    evt = TrackerEvent(
        kind=TrackerEventKind.UPDATED, ref=ref(), changed_fields=["closed"], at=datetime.now(UTC)
    )
    await loop.on_event(evt)
    [msg] = n.sent
    assert msg.handle == "sam" and msg.subject == "🎉 #12 ist erledigt. Wie hast Du es gelöst?"
    assert "auf Englisch" in msg.text and msg.ref == ref()
    await loop.on_event(evt)  # second close event (e.g. reopened + closed): no second ask
    assert len(n.sent) == 1


async def test_howto_loop_skips_when_howto_exists() -> None:
    c = cfg()
    t = tracker(TaskStatus.DONE)
    n = RecordingNotifier()
    md = render_howto(
        Analysis(kind="solution", fix="x"),
        ticket_language="en",
        author="Sam",
        channel="email",
        source_language="en",
    )
    from agentic_pm.adapters import AuditMeta, Channel

    await t.add_comment(ref(), md, AuditMeta(actor="sam", channel=Channel.EMAIL, reason="how-to"))
    assert await HowToLoop(c, Guard(c, t, n), n).ask(ref()) == []


# ------------------------------------------------------------- notifier/imap


def test_email_notifier_sets_routing_headers() -> None:
    sent: list[EmailMessage] = []
    msg = EmailNotifier(cfg(), send=sent.append).build(
        "sam", "Hi", "text", ref=ref(), in_reply_to="<x@y>"
    )
    assert msg is not None
    assert msg["Reply-To"] == "pm+12@acme.test" and msg["From"] == "pm@acme.test"
    assert ref_from_message_ids(str(msg["Message-ID"])) == ref()
    assert msg["In-Reply-To"] == "<x@y>"


class FakeImap:
    def __init__(self, messages: dict[bytes, bytes]) -> None:
        self.messages = messages
        self.seen: list[bytes] = []

    def __call__(self, host: str, port: int) -> "FakeImap":
        return self

    def login(self, *_: str) -> None: ...
    def select(self, *_: str) -> None: ...
    def logout(self) -> None: ...

    def uid(self, cmd: str, *args: Any) -> Any:
        if cmd == "search":
            return "OK", [b" ".join(u for u in self.messages if u not in self.seen)]
        if cmd == "fetch":
            return "OK", [(b"1 (BODY[] {n}", self.messages[args[0]]), b")"]
        if cmd == "store":
            self.seen += args[0].split(b",")
            return "OK", []
        raise AssertionError(cmd)


async def test_poll_once_marks_seen_after_handling() -> None:
    r, _, _ = router(None)
    imap = FakeImap({b"1": email("Status: almost done"), b"2": email("x", sender="eve@evil.test")})
    inbox = ImapInbox({"AGENT_PM_IMAP_HOST": "imap.test"}, connect=imap)
    assert await poll_once(inbox, r, r.cfg) == ["note", "ignored_unknown_sender"]
    assert imap.seen == [b"1", b"2"]
    assert await poll_once(inbox, r, r.cfg) == []
