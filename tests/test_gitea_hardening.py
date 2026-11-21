"""Regressions for the Gitea maintainer's #65 hardening review."""

import hashlib
import hmac
import json

import httpx
import pytest

from agentic_pm.adapters.base import TaskRef
from agentic_pm.adapters.gitea import GiteaAdapter, GiteaError, verify_signature


def test_empty_secret_cannot_authenticate() -> None:
    body = b"{}"
    signature = hmac.new(b"", body, hashlib.sha256).hexdigest()
    assert not verify_signature("", body, signature)


@pytest.mark.parametrize(
    "project",
    [
        "../admin",
        "acme/../admin",
        "acme/app/extra",
        "acme/%2e%2e",
        "acme/app?x=y",
        "acme/app#x",
        "acme/..",
        "acme/app\\x",
    ],
)
async def test_invalid_projects_never_send_a_request(project: str) -> None:
    seen = []
    adapter = GiteaAdapter(
        "https://forge.test",
        transport=httpx.MockTransport(lambda req: seen.append(req) or httpx.Response(200, json=[])),
    )
    with pytest.raises(ValueError, match="project"):
        await adapter.list_tasks(project)
    assert seen == []
    await adapter.aclose()


@pytest.mark.parametrize(
    "issue_id", ["../admin", "1/comments", "1?x=y", "0", "-1", "1%2fcomments", "\u0661"]
)
async def test_invalid_issue_ids_never_send_a_request(issue_id: str) -> None:
    seen = []
    adapter = GiteaAdapter(
        "https://forge.test",
        transport=httpx.MockTransport(
            lambda req: (
                seen.append(req)
                or httpx.Response(200, json={"number": 1, "title": "x", "state": "open"})
            )
        ),
    )
    with pytest.raises(ValueError, match="issue"):
        await adapter.get_task(TaskRef(tracker="gitea", project="acme/app", id=issue_id))
    assert seen == []
    await adapter.aclose()


async def test_unending_pagination_raises_at_the_limit() -> None:
    seen = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(
            200, json=[], headers={"Link": '<https://forge.test/next>; rel="next"'}
        )

    adapter = GiteaAdapter("https://forge.test", transport=httpx.MockTransport(handle), max_pages=2)
    with pytest.raises(GiteaError, match="pagination"):
        await adapter.list_tasks("acme/app")
    assert len(seen) == 2
    await adapter.aclose()


async def test_token_over_remote_http_warns() -> None:
    with pytest.warns(UserWarning, match="unencrypted"):
        adapter = GiteaAdapter("http://forge.test", token="private-token")
    await adapter.aclose()


@pytest.mark.parametrize("host", ["localhost", "127.0.0.1", "[::1]"])
async def test_loopback_http_remains_supported(host: str) -> None:
    adapter = GiteaAdapter(f"http://{host}", token="local-token")
    await adapter.aclose()


async def test_webhooks_authenticate_bytes_and_bind_project_before_dispatch() -> None:
    adapter = GiteaAdapter("https://forge.test", project="acme/app")
    seen = []

    async def receive(event):
        seen.append(event)

    adapter.subscribe(receive)
    payload = {"action": "opened", "issue": {"number": 1}, "repository": {"full_name": "acme/app"}}
    body = json.dumps(payload).encode()

    def sig(data: bytes) -> str:
        return hmac.new(b"secret", data, hashlib.sha256).hexdigest()

    for secret, signature, raw in [
        ("", sig(body), body),
        ("secret", None, body),
        ("secret", "bad", body),
        ("secret", sig(body), body + b" "),
    ]:
        assert (
            await adapter.handle_webhook(
                "issues", raw, "same-id", secret=secret, signature_header=signature
            )
            is None
        )
    foreign = json.dumps({**payload, "repository": {"full_name": "other/repo"}}).encode()
    assert (
        await adapter.handle_webhook(
            "issues", foreign, "same-id", secret="secret", signature_header=sig(foreign)
        )
        is None
    )
    assert seen == [] and adapter.last_decision is None
    assert (
        await adapter.handle_webhook(
            "issues", body, "same-id", secret="secret", signature_header=sig(body)
        )
        is not None
    )
    assert len(seen) == 1
    assert (
        await adapter.handle_webhook(
            "issues", body, "same-id", secret="secret", signature_header=sig(body)
        )
        is None
    )
    await adapter.aclose()


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {"repository": []},
        {"repository": {"full_name": "acme/app"}, "issue": []},
        {"repository": {"full_name": "acme/app"}, "issue": {"number": "../admin"}},
    ],
)
async def test_malformed_authenticated_webhooks_are_ignored(payload) -> None:
    adapter = GiteaAdapter("https://forge.test", project="acme/app")
    body = json.dumps(payload).encode()
    signature = hmac.new(b"secret", body, hashlib.sha256).hexdigest()
    assert (
        await adapter.handle_webhook("issues", body, secret="secret", signature_header=signature)
        is None
    )
    assert adapter.last_decision is None
    await adapter.aclose()


async def test_unconfigured_project_does_not_receive_events() -> None:
    adapter = GiteaAdapter("https://forge.test")
    body = b'{"issue":{"number":1},"repository":{"full_name":"acme/app"}}'
    signature = hmac.new(b"secret", body, hashlib.sha256).hexdigest()
    assert (
        await adapter.handle_webhook("issues", body, secret="secret", signature_header=signature)
        is None
    )
    await adapter.aclose()


def test_page_limit_must_be_positive() -> None:
    with pytest.raises(ValueError, match="max_pages"):
        GiteaAdapter("https://forge.test", max_pages=0)


async def test_last_allowed_page_can_finish_normally() -> None:
    seen = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        headers = {"Link": '<https://forge.test/next>; rel="next"'} if len(seen) == 1 else {}
        return httpx.Response(200, json=[], headers=headers)

    adapter = GiteaAdapter("https://forge.test", transport=httpx.MockTransport(handle), max_pages=2)
    assert await adapter.list_tasks("acme/app") == []
    assert len(seen) == 2
    await adapter.aclose()
