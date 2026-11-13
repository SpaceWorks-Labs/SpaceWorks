"""L1 G1: event short links /e/<7-char base62> (promised-items SPEC section 1)."""

import re
from datetime import timedelta

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.events import short_links
from apps.events.models import EventShortLink, EventShortLinkVisitDay
from tests.events.collab_helpers import client_for, make_member, make_staff
from tests.events.ticketing_helpers import event_space, open_event

pytestmark = pytest.mark.django_db(transaction=True)
PERSON = {"HTTP_X_SW_VISIT": "1", "HTTP_USER_AGENT": "Mozilla/5.0 (X11; Linux x86_64) Firefox/131.0"}


def fixture(*, on=True):
    space = event_space("shortlinks")
    if on:
        space.enabled_features += ["events.short_links"]
        space.save(update_fields=["enabled_features"])
    return space, make_staff(space), open_event(space)


def admin(event, suffix=""):
    return f"/api/v1/admin/events/{event.pk}/short-link/{suffix}"


def resolve(code, **extra):
    return APIClient().get(f"/api/v1/public/event-codes/{code}/", **extra)


def test_code_grammar_and_one_live_code_per_event():
    space, staff, event = fixture()
    for _ in range(50):
        assert re.fullmatch(r"[0-9A-Za-z]{7}", short_links.new_code())
    first = client_for(staff).post(admin(event))
    assert first.status_code == 201 and re.fullmatch(r"[0-9A-Za-z]{7}", first.data["code"])
    assert first.data["url"].endswith(f"/e/{first.data['code']}")
    again = client_for(staff).post(admin(event))
    assert again.status_code == 200 and again.data["code"] == first.data["code"]
    with pytest.raises(IntegrityError), transaction.atomic():
        EventShortLink.objects.create(event=event, makerspace=space, code="AbCdEf1")
    assert AuditLog.objects.filter(action="event.short_link.created").count() == 1


def test_regenerate_retires_the_old_code_which_404s_and_is_never_reissued():
    _space, staff, event = fixture()
    old = client_for(staff).post(admin(event)).data["code"]
    assert resolve(old).status_code == 200
    refused = client_for(staff).post(admin(event, "regenerate/"), {"confirm": False}, format="json")
    assert refused.status_code == 400
    fresh = client_for(staff).post(admin(event, "regenerate/"), {"confirm": True}, format="json")
    assert fresh.status_code == 200 and fresh.data["code"] != old
    assert resolve(old).status_code == 404
    assert resolve(fresh.data["code"]).status_code == 200
    retired = EventShortLink.objects.get(code=old)
    assert retired.retired_at is not None and retired.retired_by_id == staff.pk
    with pytest.raises(Exception), transaction.atomic():
        EventShortLink.objects.filter(pk=retired.pk).update(retired_at=None)
    row = AuditLog.objects.get(action="event.short_link.regenerated")
    assert row.meta["retired_code"] == old and row.meta["code"] == fresh.data["code"]


@pytest.mark.parametrize("condition", ["private", "draft", "cancelled", "ended", "offline", "module_off"])
def test_resolve_has_exactly_the_public_event_gate(condition):
    space, staff, event = fixture()
    code = client_for(staff).post(admin(event)).data["code"]
    if condition == "private":
        event.is_public = False
    elif condition in {"draft", "cancelled"}:
        event.status = condition
    elif condition == "ended":
        event.starts_at, event.ends_at = timezone.now() - timedelta(hours=3), timezone.now() - timedelta(hours=1)
    elif condition == "offline":
        event.page_state = "offline"
    event.save()
    if condition == "module_off":
        space.enabled_modules.remove("events")
        space.save(update_fields=["enabled_modules"])
    assert resolve(code).status_code == 404


def test_unlisted_event_resolves_by_code_with_noindex():
    _space, staff, event = fixture()
    code = client_for(staff).post(admin(event)).data["code"]
    event.listing = "unlisted"
    event.save(update_fields=["listing"])
    response = resolve(code)
    assert response.status_code == 200 and response["X-Robots-Tag"] == "noindex, nofollow"
    assert response.data["indexable"] is False
    assert response.data["canonical_url"].endswith(f"/e/{code}")


def test_unknown_and_malformed_codes_are_uniform_404():
    assert resolve("Zz00000").status_code == 404
    assert APIClient().get("/api/v1/public/event-codes/short/").status_code == 404


def test_switch_off_hides_staff_routes_and_resolution_but_keeps_codes():
    space, staff, event = fixture()
    code = client_for(staff).post(admin(event)).data["code"]
    space.enabled_features.remove("events.short_links")
    space.save(update_fields=["enabled_features"])
    assert client_for(staff).get(admin(event)).status_code == 404
    assert client_for(staff).post(admin(event)).status_code == 404
    assert resolve(code).status_code == 404
    assert EventShortLink.objects.filter(code=code).exists()
    space.enabled_features.append("events.short_links")
    space.save(update_fields=["enabled_features"])
    assert resolve(code).status_code == 200


def test_staff_authority_publish_schedule_and_tenant_isolation():
    space, staff, event = fixture()
    member = make_member(space)
    assert client_for(member).post(admin(event)).status_code in {403, 404}
    other = event_space("othershort")
    other.enabled_features += ["events.short_links"]
    other.save(update_fields=["enabled_features"])
    assert client_for(make_staff(other)).get(admin(event)).status_code == 404
    draft = open_event(space)
    type(draft).objects.filter(pk=draft.pk).update(status="draft")
    assert client_for(staff).post(admin(draft)).status_code == 400


def test_visit_counter_counts_people_once_and_stores_no_pii():
    _space, staff, event = fixture()
    code = client_for(staff).post(admin(event)).data["code"]
    resolve(code, **PERSON)
    resolve(code, **PERSON)
    resolve(code)  # refetch without the first-load header
    resolve(code, HTTP_X_SW_VISIT="1", HTTP_USER_AGENT="facebookexternalhit/1.1")
    resolve(code, HTTP_X_SW_VISIT="1", HTTP_SEC_PURPOSE="prefetch", HTTP_USER_AGENT=PERSON["HTTP_USER_AGENT"])
    day = EventShortLinkVisitDay.objects.get(event=event)
    assert day.count == 2
    assert {field.name for field in EventShortLinkVisitDay._meta.fields} == {"id", "event", "makerspace", "day", "count"}
    series = short_links.visits(event)
    assert len(series) == 30 and series[-1]["count"] == 2
    payload = client_for(staff).get(admin(event)).data
    assert payload["total_visits"] == 2 and payload["visits_30d"][-1]["count"] == 2
    assert short_links.visits(event, since=day.day)[0]["count"] == 2


def test_counter_failure_never_breaks_resolution(monkeypatch):
    _space, staff, event = fixture()
    code = client_for(staff).post(admin(event)).data["code"]

    def boom(*args, **kwargs):
        raise RuntimeError("counter down")

    monkeypatch.setattr("apps.events.short_links.local_now", boom)
    assert resolve(code, **PERSON).status_code == 200


def test_resolve_is_rate_limited(monkeypatch):
    from apps.apiclients.throttling import ClientTierRateThrottle
    from django.conf import settings
    assert settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["event_short_link"] == "30/min"
    monkeypatch.setitem(ClientTierRateThrottle.THROTTLE_RATES, "event_short_link", "2/min")
    from django.core.cache import cache
    cache.clear()
    _space, staff, event = fixture()
    code = client_for(staff).post(admin(event)).data["code"]
    statuses = [resolve(code).status_code for _ in range(4)]
    assert statuses[:2] == [200, 200] and 429 in statuses[2:]


def test_short_code_share_card_never_counts_a_visit(settings):
    settings.PUBLIC_APP_BASE_URL = "https://testserver"
    _space, staff, event = fixture()
    code = client_for(staff).post(admin(event)).data["code"]
    response = APIClient().get(f"/share/e/{code}/", **PERSON)
    assert response.status_code == 200 and b"og:image" in response.content
    assert not EventShortLinkVisitDay.objects.filter(event=event).exists()
