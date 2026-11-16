"""A browser opening List-Unsubscribe gets a no-write landing; one-click POST is unchanged."""
from urllib.parse import quote

import pytest
from django.core import mail
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.integrations.dispatch import dispatch_email
from apps.integrations.email_preferences import unsubscribe_token, with_unsubscribe_footer
from apps.integrations.models import EmailLog
from apps.notifications.models import MemberNotificationPreference
from tests.return_helpers import make_member, make_space

pytestmark = pytest.mark.django_db


def setup(slug):
    space = make_space(slug)
    space.enabled_features = [*space.enabled_features, "notifications.member_preferences"]
    space.save(update_fields=["enabled_features"])
    user = make_member(f"{slug}-member", space)
    token = unsubscribe_token(space.pk, user.pk, "bookings")
    return space, user, token, f"/api/v1/notifications/unsubscribe/{token}"


def nothing_written(user):
    return (not MemberNotificationPreference.objects.filter(user=user).exists()
            and not AuditLog.objects.filter(action="notification.unsubscribed").exists())


def test_get_redirects_to_the_website_page_and_changes_nothing(settings):
    settings.PUBLIC_APP_BASE_URL = "https://makers.example/"
    _space, user, token, path = setup("get-redirect")
    response = APIClient().get(path)
    assert response.status_code == 302
    assert response["Location"] == f"https://makers.example/unsubscribe/{quote(token, safe='')}"
    assert nothing_written(user)


def test_post_still_unsubscribes_after_a_get(settings):
    settings.PUBLIC_APP_BASE_URL = "https://makers.example"
    _space, user, _token, path = setup("get-then-post")
    client = APIClient()
    assert client.get(path).status_code == 302
    response = client.post(path, "List-Unsubscribe=One-Click", content_type="application/x-www-form-urlencoded")
    assert response.status_code == 200
    assert MemberNotificationPreference.objects.filter(user=user, feature="bookings", channel="email", enabled=False).count() == 1


@pytest.mark.parametrize("base", ["https://makers.example", ""])
def test_invalid_token_is_refused_without_redirect_or_write(settings, base):
    settings.PUBLIC_APP_BASE_URL = base
    _space, user, token, path = setup(f"get-invalid-{bool(base)}")
    response = APIClient().get(path + "x")
    assert response.status_code == 400
    assert "Location" not in response and response["Content-Type"].startswith("text/html")
    assert nothing_written(user)


def test_api_only_install_renders_a_confirm_form_posting_one_click(settings):
    settings.PUBLIC_APP_BASE_URL = ""
    _space, user, _token, path = setup("get-api-only")
    client = APIClient()
    response = client.get(path)
    assert response.status_code == 200 and response["Content-Type"].startswith("text/html")
    html = response.content.decode()
    assert '<form method="post" action="">' in html
    assert 'name="List-Unsubscribe" value="One-Click"' in html
    assert response["Cache-Control"] == "no-store"
    assert nothing_written(user)
    # The form's submission is exactly the RFC 8058 body the POST already accepts.
    assert client.post(path, "List-Unsubscribe=One-Click", content_type="application/x-www-form-urlencoded").status_code == 200
    assert MemberNotificationPreference.objects.filter(user=user, feature="bookings", enabled=False).exists()


def test_optional_mail_gets_a_visible_footer_link_to_the_website_page(settings):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    settings.PUBLIC_APP_BASE_URL = "https://makers.example"
    space, user, _token, _path = setup("get-footer")
    # Same optional family/event the f2 suite sends and opts out of.
    log = dispatch_email(makerspace=space, to_email=user.email, recipient_id=user.pk, feature="hardware_requests",
                         subject="Update", text_body="Own request update", html_body="<html><body><p>Hi</p></body></html>",
                         stream="hardware", event="request_accepted", sync=True)
    assert log.status == "sent"
    sent = mail.outbox[-1]
    assert "Unsubscribe from these emails: https://makers.example/unsubscribe/" in sent.body
    html = sent.alternatives[0][0]
    assert 'href="https://makers.example/unsubscribe/' in html and html.rstrip().endswith("</body></html>")
    # Added at send time only; the stored body is untouched.
    assert "unsubscribe" not in EmailLog.objects.get(pk=log.pk).text_body.lower()


def test_footer_is_omitted_for_mandatory_mail_and_without_https(settings):
    settings.PUBLIC_APP_BASE_URL = "https://makers.example"
    space, user, _token, _path = setup("get-footer-mandatory")
    log = EmailLog(makerspace=space, recipient=user, feature="hardware_requests", stream="hardware",
                   event="return_reminder", to_email=user.email, subject="Due")
    assert with_unsubscribe_footer(log, "Return it", "") == ("Return it", "")
    log.stream, log.event, log.feature = "bookings", "confirmed", "bookings"
    settings.PUBLIC_APP_BASE_URL = "http://localhost:5000"
    assert with_unsubscribe_footer(log, "Booked", "") == ("Booked", "")
