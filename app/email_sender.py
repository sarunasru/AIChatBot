"""All outbound email lives in this module.

The rest of the application only ever calls `send_contact_email()`. Mail is sent
through an SMTP relay configured via the SMTP_* variables in .env (e.g. an
institutional @vu.lt server, or any mailbox provider's SMTP), so changing where
mail comes from is a config change here, not a change to the calling code.
"""

import logging
import smtplib
from email.message import EmailMessage

from app.config import settings

logger = logging.getLogger("faq_assistant")


class EmailConfigError(Exception):
    """Raised when the email backend is misconfigured (missing host/addresses)."""


class EmailSendError(Exception):
    """Raised when the SMTP server fails to accept the message."""


def send_contact_email(subject: str, body: str, reply_to: str) -> None:
    """Send a plain-text staff-contact email through the configured SMTP relay.

    Args:
        subject: Email subject line.
        body: Plain-text body (the user's message plus the chat transcript).
        reply_to: The visitor's email, set as Reply-To so staff can respond.

    Raises:
        EmailConfigError: if required SMTP settings are missing.
        EmailSendError: if the SMTP server rejects or fails to send the message.
    """
    if not settings.contact_to_email or not settings.contact_from_email:
        raise EmailConfigError(
            "CONTACT_TO_EMAIL ir CONTACT_FROM_EMAIL turi būti nustatyti .env faile."
        )
    if not settings.smtp_host:
        raise EmailConfigError("SMTP_HOST nenustatytas .env faile.")

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = settings.contact_from_email
    message["To"] = settings.contact_to_email
    message["Reply-To"] = reply_to
    message.set_content(body)

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=settings.request_timeout) as server:
            if settings.smtp_use_tls:
                server.starttls()
            if settings.smtp_username:
                server.login(settings.smtp_username, settings.smtp_password)
            server.send_message(message)
    except (smtplib.SMTPException, OSError) as exc:
        logger.error("SMTP send failed: %s", exc)
        raise EmailSendError("Nepavyko išsiųsti žinutės per el. pašto serverį.") from exc
