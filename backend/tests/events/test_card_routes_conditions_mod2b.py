"""MOD-2B: event ID-card, card-job, door-scan and badge-desk routes, every refusal with its exact status and code.

Order of refusal (decision 183B/221e): a foreign or signed-out caller never learns which switches are off, so
visibility and role are decided before the module or capability answers `module_disabled` / `feature_disabled`.
"""
from uuid import uuid4

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.events.models import Event, EventBadgePrint, EventIdCard
from tests.l3_local.helpers import client
from tests.parity_0120.e_b2.helpers import FEATURES, issue_cards, live_event, publish_badge, register
from tests.refusal_helpers_mod2b import error_code, feature_off, module_off, refused

pytestmark = pytest.mark.django_db
API = "/api/v1/admin"
SIGNED_OUT = (401, "not_authenticated")
FOREIGN = (404, "not_found")
PLAIN_MEMBER = (403, "permission_denied")
NAMES = ["list", "issue", "extras", "jobs-list", "jobs-create", "scan", "role", "revoke", "download",
         "photo-presign", "photo-finalize", "desk", "receipts"]


class World:
    pass


def world(slug):
    w = World()
    w.space, w.event, w.sm = live_event(slug, FEATURES)
    publish_badge(w.space, w.event, w.sm)
    w.attendee, w.registration = register(w.space, w.event, "ada")
    w.card = issue_cards(w.event)[w.registration.pk]
    _space, _event, w.outsider = live_event(slug + "-x", FEATURES)
    return w


def routes(w):
    e, c = w.event.pk, w.card.pk
    # name -> (method, url, body). The door scan needs only the events module, not the id-cards capability.
    return {
        "list": ("get", f"{API}/events/{e}/id-cards", None),
        "issue": ("post", f"{API}/events/{e}/id-cards", None),
        "extras": ("get", f"{API}/events/{e}/id-cards/extras", None),
        "jobs-list": ("get", f"{API}/events/{e}/card-jobs", None),
        "jobs-create": ("post", f"{API}/events/{e}/card-jobs", {"kind": "bulk_sheet"}),
        "scan": ("post", f"{API}/events/{e}/check-in/card-scan", {"payload": "x"}),
        "role": ("patch", f"{API}/event-id-cards/{c}", {"role": "mentor"}),
        "revoke": ("post", f"{API}/event-id-cards/{c}/revoke", {"reason": "Left"}),
        "download": ("get", f"{API}/event-id-cards/{c}/download", None),
        "photo-presign": ("post", f"{API}/event-id-cards/{c}/photo", {"content_type": "image/png"}),
        "photo-finalize": ("put", f"{API}/event-id-cards/{c}/photo", {"object_key": "x", "holder_consented": True}),
        "desk": ("get", f"{API}/events/{e}/badges/desk", None),
        "receipts": ("post", f"{API}/events/{e}/badges/print-receipts", {"receipts": [{
            "operation_id": str(uuid4()), "registration_id": w.registration.pk, "stock": "a6-portrait",
            "role": "attendee", "printed_at": timezone.now().isoformat()}]}),
    }


def call(user, route):
    method, url, body = route
    api = client(user) if user is not None else APIClient()
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
    w = world("cc-roles-" + name)
    route = routes(w)[name]
    refused(call(None, route), *SIGNED_OUT)
    refused(call(w.outsider, route), *FOREIGN)
    refused(call(w.attendee, route), *PLAIN_MEMBER)
    w.card.refresh_from_db()
    assert w.card.status == "active" and w.card.role != "mentor"
    assert not AuditLog.objects.filter(action__in=("event_card.revoked", "event_card.role_changed")).exists()


@pytest.mark.parametrize("name", NAMES)
def test_events_module_off_is_a_typed_module_disabled_404_and_back_on_restores(name):
    w = world("cc-module-" + name)
    route = routes(w)[name]
    set_events_module(w.space, False)
    module_off(call(w.sm, route))
    refused(call(w.outsider, route), *FOREIGN)  # a foreign caller learns nothing about the switch
    set_events_module(w.space, True)
    assert error_code(call(w.sm, route)) not in ("module_disabled", "feature_disabled")


@pytest.mark.parametrize("name", [n for n in NAMES if n != "scan"])
def test_id_cards_capability_off_is_a_typed_feature_disabled_404_and_back_on_restores(name):
    w = world("cc-feature-" + name)
    route = routes(w)[name]
    set_features(w.space, off=("events.id_cards",))
    feature_off(call(w.sm, route))
    refused(call(w.outsider, route), *FOREIGN)
    refused(call(w.attendee, route), *PLAIN_MEMBER)
    set_features(w.space, on=("events.id_cards",))
    assert error_code(call(w.sm, route)) != "feature_disabled"


def test_the_door_scan_still_works_with_the_id_cards_capability_off():
    w = world("cc-scan-off")
    set_features(w.space, off=("events.id_cards",))
    # An unknown code is a plain 404 either way; the switch must not change the answer or make it typed.
    response = call(w.sm, routes(w)["scan"])
    refused(response, 404, "not_found")
    set_features(w.space, on=("events.id_cards",))
    refused(call(w.sm, routes(w)["scan"]), 404, "not_found")


@pytest.mark.parametrize("name", ["desk", "receipts"])
def test_badge_desk_print_capability_off_is_feature_disabled_while_id_cards_stay_on(name):
    w = world("cc-desk-off-" + name)
    set_features(w.space, off=("events.badge_desk_print",))
    feature_off(call(w.sm, routes(w)[name]))
    assert call(w.sm, routes(w)["list"]).status_code == 200
    set_features(w.space, on=("events.badge_desk_print",))
    assert call(w.sm, routes(w)[name]).status_code == 200


def test_card_list_shows_only_this_events_cards():
    w = world("cc-list")
    other = Event.objects.create(makerspace=w.space, title="Other", status="published",
                                 starts_at=w.event.starts_at, ends_at=w.event.ends_at)
    assert [row["id"] for row in call(w.sm, routes(w)["list"]).json()] == [w.card.pk]
    assert call(w.sm, ("get", f"{API}/events/{other.pk}/id-cards", None)).json() == []


def test_issue_cards_is_idempotent_and_audits_each_new_card_once():
    w = world("cc-issue")
    _user, second = register(w.space, w.event, "bob")
    first = call(w.sm, routes(w)["issue"])
    assert first.status_code == 200 and first.json() == {"issued": 1, "revoked": 0}
    assert call(w.sm, routes(w)["issue"]).json() == {"issued": 0, "revoked": 0}
    assert EventIdCard.objects.filter(registration=second).count() == 1
    assert AuditLog.objects.filter(action="event_card.issued", makerspace=w.space).count() == 2  # ada + bob


def test_role_change_audits_once_and_an_unknown_role_is_a_400_that_changes_nothing():
    w = world("cc-role")
    url = f"{API}/event-id-cards/{w.card.pk}"
    assert client(w.sm).patch(url, {"role": "emperor"}, format="json").status_code == 400
    w.card.refresh_from_db()
    assert w.card.role != "emperor"
    assert client(w.sm).patch(url, {"role": "mentor"}, format="json").json()["role"] == "mentor"
    assert AuditLog.objects.filter(action="event_card.role_changed", target_id=str(w.card.pk)).count() == 1


def test_revoke_needs_a_reason_audits_once_and_a_second_revoke_does_not_repeat_the_audit():
    w = world("cc-revoke")
    url = f"{API}/event-id-cards/{w.card.pk}/revoke"
    assert client(w.sm).post(url, {}, format="json").status_code == 400
    assert client(w.sm).post(url, {"reason": "  "}, format="json").status_code == 400
    assert client(w.sm).post(url, {"reason": "Left"}, format="json").json()["status"] == "revoked"
    assert client(w.sm).post(url, {"reason": "Left"}, format="json").json()["status"] == "revoked"
    assert AuditLog.objects.filter(action="event_card.revoked", target_id=str(w.card.pk)).count() == 1


def test_a_revoked_card_takes_no_new_photo_and_a_non_image_type_is_a_400():
    w = world("cc-photo")
    url = f"{API}/event-id-cards/{w.card.pk}/photo"
    ok = client(w.sm).post(url, {"content_type": "image/png"}, format="json")
    assert ok.status_code == 201 and "object_key" in ok.json()
    assert client(w.sm).post(url, {"content_type": "text/html"}, format="json").status_code == 400
    client(w.sm).post(f"{API}/event-id-cards/{w.card.pk}/revoke", {"reason": "Left"}, format="json")
    assert client(w.sm).post(url, {"content_type": "image/png"}, format="json").status_code == 400


def test_bulk_job_rejects_an_unknown_kind_and_is_queued_once_for_the_same_request():
    w = world("cc-jobs")
    url = f"{API}/events/{w.event.pk}/card-jobs"
    assert client(w.sm).post(url, {"kind": "origami"}, format="json").status_code == 400
    first = client(w.sm).post(url, {"kind": "bulk_sheet"}, format="json")
    assert first.status_code == 201, first.content
    second = client(w.sm).post(url, {"kind": "bulk_sheet"}, format="json")
    assert second.status_code == 200 and second.json()["id"] == first.json()["id"]
    assert len(client(w.sm).get(url).json()) == 1


def test_badge_receipts_reject_more_than_two_hundred_and_record_one_exactly_once():
    w = world("cc-receipts")
    url = f"{API}/events/{w.event.pk}/badges/print-receipts"
    one = {"operation_id": str(uuid4()), "registration_id": w.registration.pk, "stock": "a6-portrait",
           "role": "attendee", "printed_at": timezone.now().isoformat()}
    too_many = [{**one, "operation_id": str(uuid4())} for _ in range(201)]
    assert client(w.sm).post(url, {"receipts": too_many}, format="json").status_code == 400
    assert EventBadgePrint.objects.filter(event=w.event).count() == 0
    assert client(w.sm).post(url, {"receipts": [one]}, format="json").json() == {"recorded": 1, "duplicates": 0}
    assert client(w.sm).post(url, {"receipts": [one]}, format="json").json() == {"recorded": 0, "duplicates": 1}
    assert AuditLog.objects.filter(action="event_badge.printed").count() == 1


def test_badge_desk_rejects_an_unknown_status_set_and_a_foreign_registration_id():
    w = world("cc-desk")
    url = f"{API}/events/{w.event.pk}/badges/desk"
    assert client(w.sm).get(url + "?status_set=everyone").status_code == 400
    assert client(w.sm).get(url + "?registration_id=abc").status_code == 400
    assert client(w.sm).get(url + "?registration_id=99999999").status_code == 404
