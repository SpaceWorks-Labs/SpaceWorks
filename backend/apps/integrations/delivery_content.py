"""Transient SMTP content never writes mapped, encrypted model attributes."""

from dataclasses import dataclass


@dataclass(frozen=True)
class EmailContent:
    to_email: str
    subject: str
    text_body: str
    html_body: str = ""


def recipient_address(log):
    rendered = getattr(log, "_rendered_email", None)
    return log.to_email if rendered is None else rendered.to_email


def content(log):
    rendered = getattr(log, "_rendered_email", None)
    if rendered is not None:
        return rendered
    return EmailContent(log.to_email, log.subject, log.text_body, log.html_body)


def render(log, *, subject, text_body, html_body="", to_email=None):
    # Ordinary assignments to mapped fields invalidate the decrypted-value cache;
    # strict PII reads then reject that plaintext, even on an unsaved instance.
    log._rendered_email = EmailContent(
        log.to_email if to_email is None else to_email, subject, text_body, html_body,
    )
