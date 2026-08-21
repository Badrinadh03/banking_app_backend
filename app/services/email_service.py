import smtplib
from email.message import EmailMessage

from app.config import settings


def send_email(to_address: str, subject: str, body: str) -> tuple[bool, str | None]:
    """Attempts real SMTP delivery. Returns (delivered, error_message).

    If SMTP isn't configured, returns (False, None) without raising —
    callers treat that as "simulated only", not a failure.
    """
    if not settings.email_sending_enabled:
        return False, None

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = settings.smtp_from_email or settings.smtp_username
    message["To"] = to_address
    message.set_content(body)

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as server:
            if settings.smtp_use_tls:
                server.starttls()
            server.login(settings.smtp_username, settings.smtp_password)
            server.send_message(message)
        return True, None
    except Exception as exc:  # noqa: BLE001 - never let email failures break a transaction
        return False, str(exc)
