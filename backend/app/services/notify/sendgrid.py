"""
SendGrid email notification provider.

Ported from TypeScript src/notify/sendgrid.ts
"""
from __future__ import annotations

import re

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Content

from app.services.notify.base import NotifyProviderInterface

_MD_TO_HTML = [
    (re.compile(r"^### (.*)$", re.MULTILINE), r"<h3>\1</h3>"),
    (re.compile(r"^## (.*)$", re.MULTILINE), r"<h2>\1</h2>"),
    (re.compile(r"^# (.*)$", re.MULTILINE), r"<h1>\1</h1>"),
    (re.compile(r"^- (.*)$", re.MULTILINE), r"<li>\1</li>"),
]


def _md_to_html(md: str) -> str:
    for pattern, repl in _MD_TO_HTML:
        md = pattern.sub(repl, md)
    md = md.replace("\n\n", "<br/><br/>")
    return md


class SendGridProvider(NotifyProviderInterface):
    name = "SendGrid"

    def __init__(self, api_key: str) -> None:
        self.client = SendGridAPIClient(api_key)

    async def send(
        self,
        from_addr: str,
        to_addr: str,
        subject: str,
        body: str,
        html_body: str | None = None,
    ) -> None:
        html = html_body or _md_to_html(body)
        message = Mail(
            from_email=from_addr,
            to_emails=to_addr,
            subject=subject,
            html_content=Content(
                "text/html",
                f'<div style="font-family: sans-serif;">{html}</div>',
            ),
        )
        # SendGrid's client.send is synchronous — don't await it
        response = self.client.send(message)  # type: ignore[call-overload]
        if response.status_code not in (200, 201, 202):
            raise RuntimeError(f"SendGrid error: {response.status_code}")