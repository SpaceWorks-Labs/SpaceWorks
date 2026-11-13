"""SECFIX-A F4: display-screen security (H3, M18 / decision 335d, L-D2, L-D3, L-D4).

Every fix has an attack case and a normal case. Fixtures come from the SPACE-DISPLAY lane on purpose
(imported, so this package needs no conftest of its own).
"""
import logging
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.events.middleware import redact_bearer_uri
from apps.events.models import Event
from apps.makerspaces.models import Makerspace
from apps.presence import display_pairing, views_display_admin
from apps.presence.models_display import DisplayScreen
from apps.presence.public_feed import calendar_events, parse_month
from config.log_setup import RequestIdFilter
from tests.parity_0120.space_display.conftest import isolate, lane  # noqa: F401 - shared fixtures

pytestmark = pytest.mark.django_db
REGISTER = "/api/v1/space-displays/register/"
STATE = "/api/v1/space-displays/state/"


@pytest.fixture
def links(lane, settings):  # noqa: F811 - the imported fixture
    settings.PUBLIC_APP_BASE_URL = "https://spaces.example.test"
    return lane


def _admin(space, tail=""):
    return f"/api/v1/admin/makerspace/{space.pk}/presence-displays{tail}"


def _register(lane, ip="203.0.113.7"):  # noqa: F811
    response = lane.client().post(REGISTER, REMOTE_ADDR=ip)
    return response


def _poll(lane, token, scheme="Display"):  # noqa: F811
    return lane.client().get(STATE, HTTP_AUTHORIZATION=f"{scheme} {token}")


# --- H3: provision and New address work (encrypt_value is imported) -------------------------------------

def test_provision_and_rotate_issue_working_addresses(links):
    admin = links.client(links.staff)
    made = admin.post(_admin(links.space, "/link"), {"name": "Lobby"}, format="json")
    assert made.status_code == 201
    old = made.json()["url"].split("#k=")[1]
    assert _poll(links, old).json()["state"] == "paired"
    rotated = admin.post(_admin(links.space, f"/{made.json()['id']}/link"))
    assert rotated.status_code == 200
    new = rotated.json()["url"].split("#k=")[1]
    assert new != old
    assert _poll(links, old).status_code == 404  # the leaked address is dead at once
    assert _poll(links, new).status_code == 200
    assert AuditLog.objects.filter(action="presence.display_link_rotated", makerspace=links.space).count() == 1


# --- M18 / 335(d): the secret travels in a header on a fixed path ---------------------------------------

def test_header_poll_works_and_is_not_cached(lane):  # noqa: F811
    token = _register(lane).json()["token"]
    response = _poll(lane, token)
    assert response.status_code == 200 and response.json()["state"] == "unclaimed"
    assert response["Cache-Control"] == "no-store"
    assert _poll(lane, token, scheme="display").status_code == 200  # the scheme is case-insensitive


@pytest.mark.parametrize("header", [None, "", "Display ", "Bearer {t}", "{t}", "Display not-a-real-secret"])
def test_header_poll_refuses_anything_but_the_display_scheme(lane, header):  # noqa: F811
    token = _register(lane).json()["token"]
    extra = {} if header is None else {"HTTP_AUTHORIZATION": header.format(t=token)}
    assert lane.client().get(STATE, **extra).status_code == 404


def test_revoked_screen_gets_the_same_404_on_the_header_route(lane):  # noqa: F811
    body = _register(lane).json()
    admin = lane.client(lane.staff)
    row_id = admin.post(_admin(lane.space), {"code": body["code"]}, format="json").json()["id"]
    assert _poll(lane, body["token"]).json()["state"] == "paired"
    admin.delete(_admin(lane.space, f"/{row_id}"))
    assert _poll(lane, body["token"]).status_code == 404


def test_old_path_still_answers_but_its_secret_never_reaches_the_request_line(lane):  # noqa: F811
    token = _register(lane).json()["token"]
    path = f"/api/v1/space-displays/{token}/state/"
    response = lane.client().get(path, RAW_URI=path)
    assert response.status_code == 200 and response.json()["state"] == "unclaimed"
    meta = response.wsgi_request.META
    assert token not in meta["PATH_INFO"] and token not in meta["RAW_URI"]
    assert "/space-displays/[redacted]/state/" in meta["RAW_URI"]


def test_django_request_log_lines_are_redacted():
    record = logging.LogRecord("django.request", logging.WARNING, __file__, 1, "Not Found: %s", (
        "/api/v1/space-displays/SuperSecretToken_123/state/",), None)
    RequestIdFilter().filter(record)
    assert "SuperSecretToken_123" not in record.getMessage()
    assert "[redacted]" in record.getMessage()


def test_redaction_leaves_the_fixed_and_register_paths_alone():
    for path in ("/api/v1/space-displays/state/", "/api/v1/space-displays/register/"):
        assert redact_bearer_uri(f"GET {path} HTTP/1.1") == f"GET {path} HTTP/1.1"
    assert redact_bearer_uri("GET /api/v1/space-displays/abc-_9/state/?x=1 HTTP/1.1") == (
        "GET /api/v1/space-displays/[redacted]/state/?x=1 HTTP/1.1")


# --- L-D3: the secret-bearing address is not re-readable ------------------------------------------------

def test_list_and_patch_never_return_the_address(links):
    admin = links.client(links.staff)
    made = admin.post(_admin(links.space, "/link"), {"name": "Lobby"}, format="json").json()
    secret = made["url"].split("#k=")[1]
    listed = admin.get(_admin(links.space)).json()["displays"]
    assert listed[0]["has_link"] is True and listed[0]["url"] == ""
    patched = admin.patch(_admin(links.space, f"/{made['id']}"), {"name": "Hall"}, format="json")
    assert patched.status_code == 200 and patched.json()["url"] == ""
    for body in (admin.get(_admin(links.space)).content, patched.content):
        assert secret.encode() not in body


def test_code_paired_screens_have_no_link(lane):  # noqa: F811
    code = _register(lane).json()["code"]
    claimed = lane.client(lane.staff).post(_admin(lane.space), {"code": code}, format="json").json()
    assert claimed["has_link"] is False and claimed["url"] == ""


# --- L-D2: claim throttles, failed-claim audit, per-network registry budget -----------------------------

def test_wrong_codes_spend_the_space_budget_and_are_audited(lane, monkeypatch):  # noqa: F811
    monkeypatch.setattr(display_pairing, "CLAIM_FAILURES_PER_SPACE", 3)
    good = _register(lane).json()["code"]
    admin = lane.client(lane.staff)
    for wrong in ("AAAAAA", "BBBBBB", "CCCCCC"):
        assert admin.post(_admin(lane.space), {"code": wrong}, format="json").status_code == 404
    assert AuditLog.objects.filter(action="presence.display_claim_failed", makerspace=lane.space).count() == 3
    refused = admin.post(_admin(lane.space), {"code": good}, format="json")
    assert refused.status_code == 429 and refused.json()["code"] == "display_claim_throttled"
    assert DisplayScreen.objects.get(pairing_code=good).makerspace_id is None


def test_space_budget_is_per_space(lane, monkeypatch):  # noqa: F811
    monkeypatch.setattr(display_pairing, "CLAIM_FAILURES_PER_SPACE", 1)
    lane.client(lane.staff).post(_admin(lane.space), {"code": "AAAAAA"}, format="json")
    other = Makerspace.objects.create(name="Other", slug="display-other", enabled_modules=lane.space.enabled_modules,
                                      enabled_features=lane.space.enabled_features)
    manager = lane.person("other-manager", manager=True, target=other)
    code = _register(lane).json()["code"]
    assert lane.client(manager).post(_admin(other), {"code": code}, format="json").status_code == 201


def test_claims_are_throttled_per_person_but_listing_is_not(lane, monkeypatch):  # noqa: F811
    monkeypatch.setattr(views_display_admin.DisplayClaimThrottle, "rate", "2/hour")
    admin = lane.client(lane.staff)
    for wrong in ("AAAAAA", "BBBBBB"):
        assert admin.post(_admin(lane.space), {"code": wrong}, format="json").status_code == 404
    code = _register(lane).json()["code"]
    assert admin.post(_admin(lane.space), {"code": code}, format="json").status_code == 429
    for _ in range(4):
        assert admin.get(_admin(lane.space)).status_code == 200


def test_one_network_cannot_fill_the_registry(lane, monkeypatch):  # noqa: F811
    monkeypatch.setattr(display_pairing, "MAX_UNCLAIMED_PER_NETWORK", 3)
    for _ in range(3):
        assert _register(lane, ip="2001:db8:1:2::10").status_code == 201
    refused = _register(lane, ip="2001:db8:1:2::99")  # same /64, different address
    assert refused.status_code == 429 and refused.json()["code"] == "display_registry_full"
    assert _register(lane, ip="2001:db8:1:3::10").status_code == 201  # another /64 is unaffected
    assert _register(lane, ip="198.51.100.4").status_code == 201


def test_network_of_groups_ipv6_by_64_and_keeps_ipv4_exact():
    assert display_pairing.network_of("2001:db8::1") == display_pairing.network_of("2001:db8::ffff:1")
    assert display_pairing.network_of("2001:db8:0:1::1") != display_pairing.network_of("2001:db8::1")
    assert display_pairing.network_of("192.0.2.1") != display_pairing.network_of("192.0.2.2")
    assert display_pairing.network_of("::ffff:192.0.2.1") == "192.0.2.1"
    assert display_pairing.network_of("garbage") == "unknown"


# --- L-D4: the display calendar matches the public listing; far months do not 500 -----------------------

def _event(lane, title, start, end, status="published"):  # noqa: F811
    return Event.objects.create(makerspace=lane.space, title=title, status=status, starts_at=start, ends_at=end,
                                is_public=True)


def test_calendar_omits_finished_events_like_the_public_listing(lane):  # noqa: F811
    now = timezone.now()
    _event(lane, "Finished", now - timedelta(hours=3), now - timedelta(hours=1), status="completed")
    _event(lane, "Ended published", now - timedelta(hours=3), now - timedelta(hours=1))
    _event(lane, "Soon", now + timedelta(hours=1), now + timedelta(hours=2))
    month = timezone.localtime(now - timedelta(hours=1)).strftime("%Y-%m")
    titles = {e["title"] for e in calendar_events(lane.space, month, now=now)["events"]}
    assert "Finished" not in titles and "Ended published" not in titles
    soon_month = timezone.localtime(now + timedelta(hours=1)).strftime("%Y-%m")
    assert "Soon" in {e["title"] for e in calendar_events(lane.space, soon_month, now=now)["events"]}


@pytest.mark.parametrize("value", ["9999-12", "0001-01", "1-1", "2026-13", "x", None])
def test_out_of_range_months_fall_back_to_this_month(lane, value):  # noqa: F811
    today = timezone.localdate()
    assert parse_month(value, today) == today.replace(day=1)
    assert calendar_events(lane.space, value)["month"] == today.strftime("%Y-%m")


def test_a_normal_month_is_honoured():
    assert parse_month("2026-02", timezone.localdate()).isoformat() == "2026-02-01"
