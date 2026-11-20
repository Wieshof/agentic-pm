"""Web control plane v0: approval pages and webhook endpoint.

* GET  /approve?t=…   shows the proposed change (never changes anything, so mail
                      scanners that pre-fetch links can't approve by accident)
* POST /approve       approve or decline (the signed token is the permission)
* POST /webhooks/github  verified with AGENT_PM_GITHUB_WEBHOOK_SECRET, then the
                      webhook gate (self-trigger protection, de-duplication)
* POST /webhooks/<source>  the same per source with several trackers (ADR-0006),
                      verified with AGENT_PM_<SOURCE>_WEBHOOK_SECRET
* GET  /healthz
"""

from __future__ import annotations

import html
import json
from collections.abc import Awaitable, Callable
from typing import Any
from urllib.parse import urlparse

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, Response
from starlette.routing import Route

from agentic_pm import i18n
from agentic_pm.actions import Guard
from agentic_pm.approvals import ExpiredToken, InvalidToken
from agentic_pm.messages import describe_patch

HEADERS = {
    "Cache-Control": "no-store",
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "DENY",
    "X-Content-Type-Options": "nosniff",
}


def _t(lang: str) -> i18n.Texts:
    return i18n.texts("web", lang)


def _page(title: str, body: str, status: int = 200) -> HTMLResponse:
    doc = (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>{html.escape(title)}</title><style>"
        "body{font-family:system-ui,sans-serif;max-width:560px;margin:40px auto;padding:0 16px;"
        "line-height:1.5;color:#1f2933}button{font-size:1rem;padding:10px 18px;margin:8px 8px 0 0;"
        "border-radius:8px;border:1px solid #cbd2d9;background:#f5f7fa;cursor:pointer}"
        ".card{background:#f4f7fb;border-radius:10px;padding:16px}</style></head>"
        f"<body>{body}</body></html>"
    )
    return HTMLResponse(doc, status_code=status, headers=HEADERS)


WebhookHandler = Callable[[str, dict[str, Any], str | None], Awaitable[Any]]


def safe_url(url: str | None) -> bool:
    """Only plain http(s) links are rendered: a tracker URL is untrusted data
    (e.g. a spreadsheet cell), and `javascript:` would run on the approval page."""
    if not url:
        return False
    parsed = urlparse(url)
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def create_app(
    guard: Guard,
    *,
    webhook_secret: str | None = None,
    on_github_webhook: WebhookHandler | None = None,
    gitea_webhook_secret: str | None = None,
    on_gitea_webhook: WebhookHandler | None = None,
    source_webhooks: dict[str, tuple[str, str | None, WebhookHandler]] | None = None,
) -> Starlette:
    """`source_webhooks`: source key -> (tracker kind "github" | "gitea", secret, handler)."""
    cfg = guard.cfg

    async def healthz(_: Request) -> Response:
        return JSONResponse({"ok": True})

    async def show(request: Request) -> Response:
        token = request.query_params.get("t", "")
        try:
            req = guard.signer.verify(token) if guard.signer else None
        except ExpiredToken:
            return _page("agent-pm", f"<p>{_t('en')['expired']}</p>", 410)
        except InvalidToken:
            return _page("agent-pm", f"<p>{_t('en')['invalid']}</p>", 400)
        if req is None:
            return _page("agent-pm", "<p>Approvals are not configured.</p>", 503)
        lang = cfg.language_of(req.approver)
        t = _t(lang)
        try:
            task = await guard.adapter.get_task(req.ref)
        except Exception:
            return _page(t["title"], f"<p>{t['error']}</p>", 502)
        change, _ = describe_patch(task, req.patch, lang)
        label = f"#{task.ref.id} {task.title}"
        if safe_url(task.url):
            label = f"<a href='{html.escape(str(task.url))}'>{html.escape(label)}</a>"
        else:
            label = html.escape(label)
        actor = cfg.display_name(req.actor) if req.actor in cfg.people else req.actor
        body = (
            f"<h2>{t['title']}, {html.escape(cfg.display_name(req.approver))} 👋</h2>"
            f"<div class='card'><p>"
            + t["intro"].format(actor=html.escape(actor), change=html.escape(change), task=label)
            + f"</p><p><strong>{t['why']}:</strong> {html.escape(req.reason)}</p></div>"
            "<form method='post' action='approve'>"
            f"<input type='hidden' name='t' value='{html.escape(token)}'>"
            f"<button name='decision' value='approve'>{t['approve']}</button>"
            f"<button name='decision' value='decline'>{t['decline']}</button></form>"
        )
        return _page(t["title"], body)

    async def decide(request: Request) -> Response:
        form = await request.form()
        token = str(form.get("t", ""))
        decision = str(form.get("decision", ""))
        if decision not in ("approve", "decline"):
            return _page("agent-pm", f"<p>{_t('en')['invalid']}</p>", 400)
        try:
            outcome = await guard.decide(token, approve=decision == "approve")
            req = guard.signer.verify(token) if guard.signer else None
        except ExpiredToken:
            return _page("agent-pm", f"<p>{_t('en')['expired']}</p>", 410)
        except InvalidToken:
            return _page("agent-pm", f"<p>{_t('en')['invalid']}</p>", 400)
        lang = cfg.language_of(req.approver) if req else "en"
        name = cfg.display_name(req.approver) if req else ""
        t = _t(lang)
        return _page(t["title"], f"<h2>{t[outcome.status].format(name=html.escape(name))}</h2>")

    def github_hook(secret: str | None, handler: WebhookHandler | None) -> Any:
        async def hook(request: Request) -> Response:
            from agentic_pm.adapters.github import verify_signature

            if not secret or handler is None:
                return JSONResponse({"error": "webhooks not configured"}, status_code=503)
            body = await request.body()
            if not verify_signature(secret, body, request.headers.get("x-hub-signature-256")):
                return JSONResponse({"error": "bad signature"}, status_code=401)
            try:
                payload = json.loads(body)
            except ValueError:
                return JSONResponse({"error": "invalid json"}, status_code=400)
            event = request.headers.get("x-github-event", "")
            result = await handler(event, payload, request.headers.get("x-github-delivery"))
            return JSONResponse({"accepted": result is not None}, status_code=202)

        return hook

    def gitea_hook(secret: str | None, handler: WebhookHandler | None) -> Any:
        async def hook(request: Request) -> Response:
            from agentic_pm.adapters.gitea import verify_signature as verify_gitea

            if not secret or handler is None:
                return JSONResponse({"error": "webhooks not configured"}, status_code=503)
            body = await request.body()
            signature = request.headers.get("x-gitea-signature") or request.headers.get(
                "x-forgejo-signature"
            )
            if not verify_gitea(secret, body, signature):
                return JSONResponse({"error": "bad signature"}, status_code=401)
            try:
                payload = json.loads(body)
            except ValueError:
                return JSONResponse({"error": "invalid json"}, status_code=400)
            event = request.headers.get("x-gitea-event") or request.headers.get(
                "x-forgejo-event", ""
            )
            delivery = request.headers.get("x-gitea-delivery") or request.headers.get(
                "x-forgejo-delivery"
            )
            result = await handler(event, payload, delivery)
            return JSONResponse({"accepted": result is not None}, status_code=202)

        return hook

    per_source = [
        Route(
            f"/webhooks/{key}",
            (gitea_hook if kind == "gitea" else github_hook)(secret, handler),
            methods=["POST"],
        )
        for key, (kind, secret, handler) in (source_webhooks or {}).items()
        if key not in ("github", "gitea")
    ]

    return Starlette(
        routes=[
            Route("/healthz", healthz),
            Route("/approve", show, methods=["GET"]),
            Route("/approve", decide, methods=["POST"]),
            Route(
                "/webhooks/github", github_hook(webhook_secret, on_github_webhook), methods=["POST"]
            ),
            Route(
                "/webhooks/gitea",
                gitea_hook(gitea_webhook_secret, on_gitea_webhook),
                methods=["POST"],
            ),
            *per_source,
        ]
    )
