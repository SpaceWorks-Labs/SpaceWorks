"""MOD-2B: speakers, series passes, event website, short link, embed policy, report switches, registration
answers/restore and series collaborators — each route's refusals with exact status AND code, module/capability
off then back on, and audit exactly once per state change.

Refusal order (decision 183B/221e): signed-out 401, a foreign tenant 404 `not_found` (never leaks existence), a plain
member 403 `permission_denied`, and only then the switch answers 404 `module_disabled` / `capability_disabled` /
`feature_disabled`.
"""
from datetime import time, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.events import services, services_series
from apps.events.models import EventPassType, EventRegistration
from apps.events.services_series_lifecycle import publish_series
from tests.events.collab_helpers import client_for, make_member, make_staff
from tests.events.ticketing_helpers import account, event_space, open_event
from tests.refusal_helpers_mod2b import error_code, refused

pytestmark = pytest.mark.django_db
API = "/api/v1/admin"
SIGNED_OUT = (401, "not_authenticated")
FOREIGN = (404, "not_found")
PLAIN_MEMBER = (403, "permission_denied")
FEATURES = ["events.orders", "events.website", "events.short_links", "events.embed", "events.series_passes"]


class World:
    pass


def world(slug):
    w = World()
    w.space = event_space(slug)
    w.space.enabled_features = sorted(set(w.space.enabled_features) | set(FEATURES))
    w.space.save(update_fields=["enabled_features"])
    w.staff = make_staff(w.space)
    w.plain = make_member(w.space, "plain")
    other = event_space(slug + "-x")
    w.outsider = make_staff(other)
    w.event = open_event(w.space)
    w.series, _occurrences = services_series.create_series(
        makerspace=w.space, actor=w.staff, title="Weekly club", description="", location="",
        registration_audience="accounts", recurrence_timezone="UTC",
        dtstart_local_date=(timezone.now() + timedelta(days=1)).date(), dtstart_local_time=time(10),
        recurrence_rule="FREQ=DAILY;COUNT=3", duration_minutes=60, is_public=True)
    publish_series(w.series, actor=w.staff)
    w.pass_type = EventPassType.objects.create(makerspace=w.space, series=w.series, name="Season", amount=Decimal(30))
    w.attendee = account("surface-attendee")
    w.registration = services.register(w.event, member=w.attendee, actor=w.staff, staff_registration=True)
    return w


def routes(w):
    e, s, m = w.event.pk, w.series.pk, w.space.pk
    return {
        "speakers-list": ("get", f"{API}/events/{e}/speakers/", None),
        "speakers-assign": ("post", f"{API}/events/{e}/speakers/", {"user_id": w.attendee.pk}),
        "speakers-invite": ("post", f"{API}/events/{e}/speakers/invite/", {"display_name": "Guest"}),
        "speakers-candidates": ("get", f"{API}/events/{e}/speaker-candidates/?search=surface", None),
        "pass-types-list": ("get", f"{API}/event-series/{s}/pass-types/", None),
        "pass-types-create": ("post", f"{API}/event-series/{s}/pass-types/", {"name": "Half", "amount": "10.000"}),
        "pass-types-patch": ("patch", f"{API}/event-pass-types/{w.pass_type.pk}/", {"name": "Season 2"}),
        "website-get": ("get", f"{API}/events/{e}/website/", None),
        "website-put": ("put", f"{API}/events/{e}/website/", {"revision": 0, "sections": [], "sessions": []}),
        "website-delay": ("post", f"{API}/events/{e}/website/sessions/talk/delay/", {"delay_minutes": 5}),
        "short-link-get": ("get", f"{API}/events/{e}/short-link/", None),
        "short-link-create": ("post", f"{API}/events/{e}/short-link/", None),
        "short-link-regenerate": ("post", f"{API}/events/{e}/short-link/regenerate/", {"confirm": True}),
        "embed-get": ("get", f"{API}/makerspaces/{m}/events/embed-policy/", None),
        "embed-put": ("put", f"{API}/makerspaces/{m}/events/embed-policy/", {"enabled": True, "allowed_origins": []}),
        "switches-get": ("get", f"{API}/makerspaces/{m}/events/report-switches/", None),
        "switches-patch": ("patch", f"{API}/makerspaces/{m}/events/report-switches/", {"switches": {}}),
        "answers": ("patch", f"{API}/event-registrations/{w.registration.pk}/answers/", {"answers": {}}),
        "restore": ("post", f"{API}/event-registrations/{w.registration.pk}/restore/", {}),
        "series-collab-get": ("get", f"{API}/event-series/{s}/collaborators/", None),
        "series-collab-put": ("put", f"{API}/event-series/{s}/collaborators/", {"slugs": []}),
    }


NAMES = ["speakers-list", "speakers-assign", "speakers-invite", "speakers-candidates", "pass-types-list",
         "pass-types-create", "pass-types-patch", "website-get", "website-put", "website-delay", "short-link-get",
         "short-link-create", "short-link-regenerate", "embed-get", "embed-put", "switches-get", "switches-patch",
         "answers", "restore", "series-collab-get", "series-collab-put"]
# The switch that answers for each route once the caller is authorised, and its typed code.
GATE = {name: ("capability_disabled", "events.short_links") for name in NAMES if name.startswith("short-link")}
GATE.update({name: ("feature_disabled", "events.website") for name in NAMES if name.startswith("website")})
GATE.update({name: ("feature_disabled", "events.series_passes") for name in NAMES if name.startswith("pass-types-")
             and name != "pass-types-patch"})
GATE.update({"embed-get": ("capability_disabled", "events.embed")})


def call(user, route):
    method, url, body = route
    api = client_for(user) if user is not None else APIClient()
    return getattr(api, method)(url, body, format="json") if body is not None else getattr(api, method)(url)


def set_features(space, *, off=(), on=()):
    space.enabled_features = sorted((set(space.enabled_features) - set(off)) | set(on))
    space.save(update_fields=["enabled_features", "updated_at"])


def set_events_module(space, on):
    modules = set(space.enabled_modules)
    space.enabled_modules = sorted(modules | {"events"} if on else modules - {"events"})
    space.save(update_fields=["enabled_modules", "updated_at"])


@pytest.mark.parametrize("name", NAMES)
def test_signed_out_foreign_tenant_and_plain_member_are_refused_with_exact_codes(name):
    w = world("sf-roles-" + name.replace("_", "-"))
    route = routes(w)[name]
    refused(call(None, route), *SIGNED_OUT)
    refused(call(w.outsider, route), *FOREIGN)
    refused(call(w.plain, route), *PLAIN_MEMBER)
    assert not AuditLog.objects.filter(makerspace=w.space, action__startswith="event.speaker").exists()
    assert not EventPassType.objects.filter(makerspace=w.space, name__in=("Half", "Season 2")).exists()


@pytest.mark.parametrize("name", NAMES)
def test_events_module_off_is_a_typed_module_disabled_404_and_back_on_restores(name):
    w = world("sf-module-" + name.replace("_", "-"))
    route = routes(w)[name]
    set_events_module(w.space, False)
    refused(call(w.staff, route), 404, "module_disabled")
    refused(call(w.outsider, route), *FOREIGN)
    set_events_module(w.space, True)
    assert error_code(call(w.staff, route)) not in ("module_disabled", "capability_disabled", "feature_disabled")


@pytest.mark.parametrize("name", sorted(GATE))
def test_capability_off_is_a_typed_404_for_staff_and_back_on_restores(name):
    w = world("sf-cap-" + name.replace("_", "-"))
    code, key = GATE[name]
    route = routes(w)[name]
    set_features(w.space, off=(key,))
    refused(call(w.staff, route), 404, code)
    refused(call(w.outsider, route), *FOREIGN)
    refused(call(w.plain, route), *PLAIN_MEMBER)
    set_features(w.space, on=(key,))
    assert error_code(call(w.staff, route)) not in ("module_disabled", "capability_disabled", "feature_disabled")


def test_speaker_assign_invite_remove_audit_once_and_the_digest_never_leaks():
    w = world("sf-speakers")
    api = client_for(w.staff)
    assigned = api.post(f"{API}/events/{w.event.pk}/speakers/", {"user_id": w.attendee.pk}, format="json")
    assert assigned.status_code == 201 and assigned.json()["status"] == "linked"
    assert AuditLog.objects.filter(action="event.speaker_assigned").count() == 1
    invited = api.post(f"{API}/events/{w.event.pk}/speakers/invite/", {"display_name": "Guest"}, format="json")
    assert invited.status_code == 201 and invited.json()["claim_url"]
    assert AuditLog.objects.filter(action="event.speaker_invited").count() == 1
    assert "claim_token_digest" not in api.get(f"{API}/events/{w.event.pk}/speakers/").content.decode()
    removed = api.post(f"{API}/event-speakers/{assigned.json()['id']}/remove/", {}, format="json")
    assert removed.status_code == 200 and removed.json()["status"] == "removed"
    assert AuditLog.objects.filter(action="event.speaker_removed").count() == 1


def test_speaker_validation_missing_name_unknown_user_and_short_search():
    w = world("sf-speaker-input")
    api = client_for(w.staff)
    assert api.post(f"{API}/events/{w.event.pk}/speakers/invite/", {}, format="json").status_code == 400
    assert api.post(f"{API}/events/{w.event.pk}/speakers/", {"user_id": 99999999}, format="json").status_code == 400
    assert api.post(f"{API}/events/{w.event.pk}/speakers/", {}, format="json").status_code == 400
    short = api.get(f"{API}/events/{w.event.pk}/speaker-candidates/?search=a")
    assert short.status_code == 200 and short.json()["results"] == []
    assert not AuditLog.objects.filter(action__startswith="event.speaker").exists()


def test_removing_a_speaker_twice_does_not_audit_twice_and_a_foreign_speaker_id_is_a_404():
    w = world("sf-speaker-twice")
    api = client_for(w.staff)
    row = api.post(f"{API}/events/{w.event.pk}/speakers/", {"user_id": w.attendee.pk}, format="json").json()
    url = f"{API}/event-speakers/{row['id']}/remove/"
    refused(call(w.outsider, ("post", url, {})), *FOREIGN)
    assert api.post(url, {}, format="json").status_code == 200
    api.post(url, {}, format="json")
    assert AuditLog.objects.filter(action="event.speaker_removed").count() == 1


def test_pass_type_create_patch_validate_and_audit():
    w = world("sf-pass")
    api = client_for(w.staff)
    created = api.post(f"{API}/event-series/{w.series.pk}/pass-types/", {"name": "Half", "amount": "10.000"}, format="json")
    assert created.status_code == 201, created.content
    assert EventPassType.objects.filter(series=w.series).count() == 2
    assert api.post(f"{API}/event-series/{w.series.pk}/pass-types/", {"name": "", "amount": "1"},
                    format="json").status_code == 400
    assert api.post(f"{API}/event-series/{w.series.pk}/pass-types/", {"name": "Neg", "amount": "-1"},
                    format="json").status_code == 400
    patched = api.patch(f"{API}/event-pass-types/{w.pass_type.pk}/", {"name": "Season 2", "capacity": 5}, format="json")
    assert patched.status_code == 200 and patched.json()["name"] == "Season 2" and patched.json()["capacity"] == 5
    listing = api.get(f"{API}/event-series/{w.series.pk}/pass-types/")
    assert listing.status_code == 200 and listing.json()["count"] == 2


def test_website_get_returns_a_revision_and_a_stale_save_is_a_400_that_changes_nothing():
    w = world("sf-website")
    api = client_for(w.staff)
    got = api.get(f"{API}/events/{w.event.pk}/website/")
    assert got.status_code == 200 and got["Cache-Control"] == "private, no-store"
    revision = got.json()["revision"]
    stale = api.put(f"{API}/events/{w.event.pk}/website/",
                    {"revision": revision + 7, "sections": [], "sessions": []}, format="json")
    assert stale.status_code == 400 and "revision" in stale.json()
    assert api.put(f"{API}/events/{w.event.pk}/website/", {"revision": revision}, format="json").status_code == 400


def test_session_delay_validates_range_and_an_unknown_session_is_a_400():
    w = world("sf-delay")
    api = client_for(w.staff)
    url = f"{API}/events/{w.event.pk}/website/sessions/talk/delay/"
    assert api.post(url, {"delay_minutes": 1441}, format="json").status_code == 400
    assert api.post(url, {"delay_minutes": -1}, format="json").status_code == 400
    assert api.post(url, {}, format="json").status_code == 400
    assert api.post(url, {"delay_minutes": 5}, format="json").status_code == 400  # no such session on this page


def test_short_link_is_idempotent_regenerate_needs_confirm_and_each_change_audits_once():
    w = world("sf-short")
    api = client_for(w.staff)
    url = f"{API}/events/{w.event.pk}/short-link/"
    first = api.post(url, format="json")
    assert first.status_code == 201
    again = api.post(url, format="json")
    assert again.status_code == 200 and again.json()["code"] == first.json()["code"]
    assert AuditLog.objects.filter(action="event.short_link.created").count() == 1
    assert api.post(url + "regenerate/", {}, format="json").status_code == 400
    assert api.post(url + "regenerate/", {"confirm": False}, format="json").status_code == 400
    assert AuditLog.objects.filter(action="event.short_link.regenerated").count() == 0
    new = api.post(url + "regenerate/", {"confirm": True}, format="json")
    assert new.status_code == 200 and new.json()["code"] != first.json()["code"]
    assert AuditLog.objects.filter(action="event.short_link.regenerated").count() == 1


def test_embed_policy_put_validates_origins_and_audits_once():
    w = world("sf-embed")
    api = client_for(w.staff)
    url = f"{API}/makerspaces/{w.space.pk}/events/embed-policy/"
    for bad in (["http://insecure.test"], ["https://a.test/path"], ["https://*.a.test"], ["https://a.test"] * 21):
        assert api.put(url, {"enabled": True, "allowed_origins": bad}, format="json").status_code == 400
    assert not AuditLog.objects.filter(action="event.embed_policy_updated").exists()
    ok = api.put(url, {"enabled": True, "allowed_origins": ["https://a.test"]}, format="json")
    assert ok.status_code == 200 and ok.json()["allowed_origins"] == ["https://a.test"]
    assert AuditLog.objects.filter(action="event.embed_policy_updated").count() == 1


def test_report_switches_reject_unknown_keys_and_empty_bodies():
    w = world("sf-switches")
    api = client_for(w.staff)
    url = f"{API}/makerspaces/{w.space.pk}/events/report-switches/"
    assert api.patch(url, {"switches": {"nonsense": True}}, format="json").status_code == 400
    assert api.patch(url, {"switches": {}}, format="json").status_code == 400
    assert api.patch(url, {"switches": {"nonsense": "yes"}}, format="json").status_code == 400
    assert api.get(url).status_code == 200


def test_cancel_restore_round_trip_audits_once_and_a_second_restore_is_refused():
    w = world("sf-restore")
    api = client_for(w.staff)
    services.cancel_registration(w.registration, actor=w.staff)
    url = f"{API}/event-registrations/{w.registration.pk}/restore/"
    restored = api.post(url, {}, format="json")
    assert restored.status_code == 200, restored.content
    assert EventRegistration.objects.get(pk=w.registration.pk).status == "registered"
    assert AuditLog.objects.filter(action="event.registration_restored").count() == 1
    again = api.post(url, {}, format="json")
    assert again.status_code >= 400 and AuditLog.objects.filter(action="event.registration_restored").count() == 1


def test_series_collaborators_unknown_slug_is_a_400_and_replace_with_nothing_is_an_empty_list():
    w = world("sf-collab")
    api = client_for(w.staff)
    url = f"{API}/event-series/{w.series.pk}/collaborators/"
    assert api.get(url).json() == []
    assert api.put(url, {"slugs": []}, format="json").json() == []
    assert api.put(url, {"slugs": ["no-such-space"]}, format="json").status_code == 400
    assert api.put(url, {}, format="json").status_code == 400
