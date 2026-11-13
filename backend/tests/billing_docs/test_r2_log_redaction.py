"""Private media URLs must not enter application or proxy access diagnostics."""
import logging
from pathlib import Path

from django.http import HttpResponse
from django.test import RequestFactory

from apps.events.middleware import CalendarFeedLogRedactionMiddleware
from apps.integrations.notification_media_secrets import redact_media_uri
from config.log_setup import RequestIdFilter


def test_media_bearer_is_redacted_before_error_log_formatting():
    token = "private-media-bearer"
    path = f"/api/v1/integrations/notification-media/{token}.pdf"
    record = logging.LogRecord("django.request", logging.WARNING, "", 0, "Not Found: %s", (path,), None)
    record.request = RequestFactory().get(path)
    assert RequestIdFilter().filter(record)
    assert token not in record.getMessage() and token not in str(record.request)
    assert "[redacted].pdf" in record.getMessage()


def test_media_view_receives_real_token_but_access_log_sources_are_redacted():
    path = "/api/v1/integrations/notification-media/private-bearer.pdf"
    request = RequestFactory().get(path, RAW_URI=path)
    seen = []
    def response(req):
        seen.append(req.path_info)
        return HttpResponse(status=404)
    CalendarFeedLogRedactionMiddleware(response)(request)
    assert seen == [path]
    for value in (request.path, request.path_info, request.META["PATH_INFO"], request.META["RAW_URI"]):
        assert "private-bearer" not in value and "[redacted].pdf" in value


def test_media_redaction_leaves_other_paths_unchanged():
    assert redact_media_uri("GET /api/v1/member/payments") == "GET /api/v1/member/payments"


def test_both_nginx_configs_suppress_media_access_and_error_logging():
    root = Path(__file__).resolve().parents[3]
    for name in ("frontend/nginx.conf", "deploy/nginx.api-only.conf"):
        content = (root / name).read_text()
        block = content.split("integrations/notification-media/", 1)[1].split("}", 1)[0]
        assert "access_log off;" in block and "error_log /dev/null;" in block
