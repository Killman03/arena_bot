from __future__ import annotations

import aiosmtplib
from email.message import EmailMessage

from app.config import settings


async def send_email_async(to_email: str, subject: str, html: str) -> None:
    """Send HTML email asynchronously using configured SMTP server."""
    message = EmailMessage()
    message["From"] = settings.email_from
    message["To"] = to_email
    message["Subject"] = subject
    message.set_content(html, subtype="html")

    await aiosmtplib.send(
        message,
        hostname=settings.smtp_host,
        port=settings.smtp_port,
        username=settings.smtp_user,
        password=settings.smtp_password,
        start_tls=True,
    )



