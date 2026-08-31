"""
SMTP email notification provider.

Ported from TypeScript src/notify/smtp.ts
"""
from __future__ import annotations

import re

import aiosmtplib
from email.message import EmailMessage

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


class SmtpProvider(NotifyProviderInterface):
    name = "SMTP"

    def __init__(
        self,
        host: str,
        port: int = 587,
        user: str = "",
        password: str = "",
        secure: bool = False,
    ) -> None:
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.secure = secure

    async def send(
        self,
        from_addr: str,
        to_addr: str,
        subject: str,
        body: str,
    ) -> None:
        html_body = _md_to_html(body)
        msg = EmailMessage()
        msg["From"] = from_addr
        msg["To"] = to_addr
        msg["Subject"] = subject
        msg.set_content(body)
        msg.add_alternative(
            f'<div style="font-family: sans-serif;">{html_body}</div>',
            subtype="html",
        )
        use_tls = self.port == 465 or self.secure
        await aiosmtplib.send(
            msg,
            hostname=self.host,
            port=self.port,
            username=self.user or None,
            password=self.password or None,
            use_tls=use_tls,
        )