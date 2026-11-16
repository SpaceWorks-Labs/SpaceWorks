import json
from unittest.mock import MagicMock, patch

import pytest
import requests
from django.core.mail import EmailMultiAlternatives

from apps.integrations.mail_providers.config import validate_config
from apps.integrations.mail_providers.connections import connection_for
from apps.integrations.smtp_validation import sanitize_email_error


CASES = [
    ("resend", {"api_key": "secret"}, {"id": "resend-id"}, 200),
    ("postmark", {"server_token": "secret"}, {"ErrorCode": 0, "MessageID": "postmark-id",
       "Message": "OK", "SubmittedAt": "2026-10-18T10:00:00Z", "To": "to@example.org"}, 200),
    ("brevo", {"api_key": "secret"}, {"messageId": "brevo-id"}, 201),
    ("mailgun", {"api_key": "secret", "domain": "mail.example.org", "region": "eu"},
       {"id": "<mailgun-id>", "message": "Queued. Thank you."}, 200),
    ("sendgrid", {"api_key": "secret"}, {}, 202),
]


def message(provider, credentials):
    config = validate_config(provider, credentials, "mail@example.org")
    connection, sender = connection_for(config)
    msg = EmailMultiAlternatives("Receipt — മലയാളം", "Plain receipt", sender,
        ["to@example.org"], cc=["cc@example.org"], bcc=["bcc@example.org"],
        reply_to=["reply@example.org"], headers={"List-Unsubscribe": "<https://example.org/unsubscribe>"},
        connection=connection)
    msg.attach_alternative("<p>Receipt</p>", "text/html")
    msg.attach("receipt.pdf", b"%PDF-receipt", "application/pdf")
    msg.spaceworks_idempotency_key = "stable-mail-key"
    return msg


@pytest.mark.parametrize("provider,credentials,body,status", CASES)
def test_http_accepts_standard_mail_and_pdf_without_smtp_kwargs(provider, credentials, body, status):
    response = requests.Response()
    response.status_code = status
    response._content = json.dumps(body).encode()
    response.headers["X-Message-Id"] = "sendgrid-id"
    msg = message(provider, credentials)
    with patch("requests.Session.request", return_value=response) as request:
        assert msg.send() == 1
    call = request.call_args
    args = dict(call.kwargs)
    # Session.post() (SendGrid) forwards ("POST", url) positionally to Session.request.
    args.setdefault("url", call.args[1] if len(call.args) > 1 else "")
    assert args["url"].startswith("https://")
    assert args["timeout"]
    # Session.post() always forwards data= and json=, one of them None.
    wire = repr(args.get("data") or args.get("json")) + repr(args.get("files"))
    assert "receipt.pdf" in wire
    assert "to@example.org" in wire and "reply@example.org" in wire
    if provider == "resend":
        assert args["headers"]["Idempotency-Key"] == "stable-mail-key"
        assert "Idempotency-Key" not in msg.extra_headers


@pytest.mark.parametrize("provider,credentials,body,status", CASES)
@pytest.mark.parametrize("failure", [401, 429, 503, "timeout"])
def test_http_failure_is_raised_and_sanitized(provider, credentials, body, status, failure):
    msg = message(provider, credentials)
    response = requests.Response()
    response.status_code = failure if isinstance(failure, int) else 200
    response._content = b'{"message":"secret provider payload","ErrorCode":401}'
    with patch("requests.Session.request", return_value=response,
               side_effect=requests.Timeout("secret token") if failure == "timeout" else None):
        with pytest.raises(Exception) as error:
            msg.send()
    assert "secret" not in sanitize_email_error(error.value)


def test_ses_uses_dedicated_session_and_no_storage_credentials(settings):
    settings.AWS_ACCESS_KEY_ID = "storage-access"
    settings.AWS_SECRET_ACCESS_KEY = "storage-secret"
    credentials = {"region": "ap-south-1", "access_key_id": "ses-access",
                   "secret_access_key": "ses-secret", "session_token": "ses-session"}
    msg = message("ses", credentials)
    with patch("apps.integrations.mail_providers.ses.boto3.session.Session") as session:
        session.return_value.client.return_value.send_email.return_value = {"MessageId": "ses-id"}
        assert msg.send() == 1
    assert session.call_args.kwargs["aws_access_key_id"] == "ses-access"
    assert session.call_args.kwargs["aws_session_token"] == "ses-session"
    config = session.return_value.client.call_args.kwargs["config"]
    assert config.retries["total_max_attempts"] == 1
    wire = session.return_value.client.return_value.send_email.call_args.kwargs
    assert b"receipt.pdf" in wire["Content"]["Raw"]["Data"]


@pytest.mark.parametrize("error", ["timeout", "auth", "throttled"])
def test_ses_failures_propagate_without_storage_fallback(error):
    from botocore.exceptions import ClientError, ReadTimeoutError
    exc = (ReadTimeoutError(endpoint_url="https://email.ap-south-1.amazonaws.com")
           if error == "timeout" else ClientError({"Error": {"Code":
           "AccessDeniedException" if error == "auth" else "TooManyRequestsException"}}, "SendEmail"))
    msg = message("ses", {"region": "ap-south-1", "access_key_id": "access", "secret_access_key": "secret"})
    with patch("apps.integrations.mail_providers.ses.boto3.session.Session") as session:
        session.return_value.client.return_value.send_email.side_effect = exc
        with pytest.raises(Exception):
            msg.send()
