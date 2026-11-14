"""MOD-2B: event ID-card, card-job, door-scan and badge-desk routes, every refusal with its exact status and code.

Order of refusal (decision 183B/221e): a foreign or signed-out caller never learns which switches are off, so
visibility and role are decided before the module or capability answers `module_disabled` / `feature_disabled`.
"""
from uuid import uuid4

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.card_designs import tokens
from apps.events.models import Event, EventBadgePrint, EventCardSettings, EventCheckInEvent, EventIdCard
from tests.l3_local.helpers import client
from tests.parity_0120.e_b2.helpers import FEATURES, issue_cards, live_event, publish_badge, register
from tests.refusal_helpers_mod2b import field_error, feature_off, module_off, refused

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
    # Q-I5: successful extras reads need the independent per-event privacy opt-in.
    EventCardSettings.objects.update_or_create(event=w.event, defaults={"extras_visible_to_organizers": True})
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
        "scan": ("post", f"{API}/events/{e}/check-in/card-scan", {"payload": tokens.url(tokens.live("event_card", w.card).token)}),
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


def assert_restored(w, name, route):
    response = call(w.sm, route)
    if name == "scan":
        assert_identified(w, response)
    elif name == "photo-finalize":
        field_error(response, "object_key", "invalid")
    elif name == "extras":
        assert response.status_code == 200 and response.json() == [], response.content
        assert response["Cache-Control"] == "private, no-store"
    else:
        expected = 201 if name in {"jobs-create", "photo-presign"} else 200
        assert response.status_code == expected, response.content
    assert EventIdCard.objects.filter(pk=w.card.pk).exists()


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
    assert_restored(w, name, route)


@pytest.mark.parametrize("name", [n for n in NAMES if n != "scan"])
def test_id_cards_capability_off_is_a_typed_feature_disabled_404_and_back_on_restores(name):
    w = world("cc-feature-" + name)
    route = routes(w)[name]
    set_features(w.space, off=("events.id_cards",))
    feature_off(call(w.sm, route))
    refused(call(w.outsider, route), *FOREIGN)
    refused(call(w.attendee, route), *PLAIN_MEMBER)
    set_features(w.space, on=("events.id_cards",))
    assert_restored(w, name, route)


def assert_identified(w, response):
    assert response.status_code == 200, response.content
    assert response.json() == {"checked_in": None, "registrations": [{
        "registration_id": w.registration.pk, "name": w.registration.name,
        "status": "registered", "confirmable": True}]}
    w.registration.refresh_from_db()
    assert w.registration.status == "registered"
    assert not EventCheckInEvent.objects.filter(registration=w.registration).exists()
    assert not AuditLog.objects.filter(makerspace=w.space, target_id=str(w.registration.pk),
        action__in=("event.registration_attended", "card.scanned_for_checkin")).exists()


def test_the_door_scan_still_works_with_the_id_cards_capability_off():
    w = world("cc-scan-off")
    route = routes(w)["scan"]
    set_features(w.space, off=("events.id_cards",))
    assert_identified(w, call(w.sm, route))
    set_features(w.space, on=("events.id_cards",))
    assert_identified(w, call(w.sm, route))


@pytest.mark.parametrize("cards_on", [False, True])
def test_door_checkin_and_replay_write_one_attendance_and_each_exact_audit(cards_on):
    w = world("cc-scan-checkin")
    method, url, body = routes(w)["scan"]
    if not cards_on:
        set_features(w.space, off=("events.id_cards",))
    assert_identified(w, call(w.sm, (method, url, body)))
    checked = call(w.sm, (method, url, {**body, "check_in": True}))
    assert checked.status_code == 200, checked.content
    row = {"registration_id": w.registration.pk, "name": w.registration.name,
           "status": "attended", "confirmable": False}
    assert checked.json() == {"checked_in": w.registration.pk, "registrations": [row]}
    replay = call(w.sm, (method, url, {**body, "check_in": True}))
    assert replay.status_code == 200 and replay.json() == {"checked_in": None, "registrations": [row]}
    w.registration.refresh_from_db()
    assert w.registration.status == "attended"
    assert EventCheckInEvent.objects.filter(registration=w.registration).count() == 1
    for action in ("event.registration_attended", "card.scanned_for_checkin"):
        assert AuditLog.objects.filter(makerspace=w.space, target_type="events.eventregistration",
            target_id=str(w.registration.pk), action=action).count() == 1


def test_door_scan_unknown_code_is_not_found():
    w = world("cc-scan-unknown")
    refused(call(w.sm, ("post", f"{API}/events/{w.event.pk}/check-in/card-scan", {"payload": "x"})),
            404, "not_found")


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
    field_error(client(w.sm).patch(url, {"role": "emperor"}, format="json"), "role", "invalid")
    w.card.refresh_from_db()
    assert w.card.role != "emperor"
    assert client(w.sm).patch(url, {"role": "mentor"}, format="json").json()["role"] == "mentor"
    assert AuditLog.objects.filter(action="event_card.role_changed", target_id=str(w.card.pk)).count() == 1


def test_revoke_needs_a_reason_audits_once_and_a_second_revoke_does_not_repeat_the_audit():
    w = world("cc-revoke")
    url = f"{API}/event-id-cards/{w.card.pk}/revoke"
    field_error(client(w.sm).post(url, {}, format="json"), "reason", "invalid")
    field_error(client(w.sm).post(url, {"reason": "  "}, format="json"), "reason", "invalid")
    assert client(w.sm).post(url, {"reason": "Left"}, format="json").json()["status"] == "revoked"
    assert client(w.sm).post(url, {"reason": "Left"}, format="json").json()["status"] == "revoked"
    assert AuditLog.objects.filter(action="event_card.revoked", target_id=str(w.card.pk)).count() == 1


def test_a_revoked_card_takes_no_new_photo_and_a_non_image_type_is_a_400():
    w = world("cc-photo")
    url = f"{API}/event-id-cards/{w.card.pk}/photo"
    ok = client(w.sm).post(url, {"content_type": "image/png"}, format="json")
    assert ok.status_code == 201 and "object_key" in ok.json()
    field_error(client(w.sm).post(url, {"content_type": "text/html"}, format="json"), "content_type", "invalid_choice")
    client(w.sm).post(f"{API}/event-id-cards/{w.card.pk}/revoke", {"reason": "Left"}, format="json")
    field_error(client(w.sm).post(url, {"content_type": "image/png"}, format="json"), "detail", "invalid")


def test_bulk_job_rejects_an_unknown_kind_and_is_queued_once_for_the_same_request():
    w = world("cc-jobs")
    url = f"{API}/events/{w.event.pk}/card-jobs"
    field_error(client(w.sm).post(url, {"kind": "origami"}, format="json"), "kind", "invalid_choice")
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
    field_error(client(w.sm).post(url, {"receipts": too_many}, format="json"), "receipts", "invalid")
    assert EventBadgePrint.objects.filter(event=w.event).count() == 0
    assert client(w.sm).post(url, {"receipts": [one]}, format="json").json() == {"recorded": 1, "duplicates": 0}
    assert client(w.sm).post(url, {"receipts": [one]}, format="json").json() == {"recorded": 0, "duplicates": 1}
    assert AuditLog.objects.filter(action="event_badge.printed").count() == 1


def test_badge_desk_rejects_an_unknown_status_set_and_a_foreign_registration_id():
    w = world("cc-desk")
    url = f"{API}/events/{w.event.pk}/badges/desk"
    field_error(client(w.sm).get(url + "?status_set=everyone"), "status_set", "invalid")
    field_error(client(w.sm).get(url + "?registration_id=abc"), "registration_id", "invalid")
    refused(client(w.sm).get(url + "?registration_id=99999999"), 404, "not_found")


@pytest.mark.parametrize("name", NAMES)
def test_manual_event_delegate_can_use_card_routes_without_tenant_staff_roles(name):
    from tests.events.staff_grant_helpers import set_grant_permissions
    from tests.events.website_helpers import grantee
    w = world("cc-grant-" + name)
    actor, grant = grantee(w.space, w.event, "edit_details")
    set_grant_permissions(grant, ["edit_details", "check_in", "manage_registrations", "publish_schedule"])
    w.sm = actor
    assert_restored(w, name, routes(w)[name])


@pytest.mark.parametrize("name", NAMES)
@pytest.mark.parametrize("role", ["organizer", "coorganizer"])
def test_organization_organizers_can_use_card_routes_without_manual_grants(name, role):
    from tests.events.test_scoped_organizer_routes_cx5 import organization_actor
    w = world("cc-org-" + role + "-" + name)
    w.sm = organization_actor(w.event, role)
    assert_restored(w, name, routes(w)[name])
    before = AuditLog.objects.filter(makerspace=w.space).count()
    refused(call(w.sm, ("get", f"{API}/makerspaces/{w.space.pk}/events/embed-policy/", None)),
            404, "not_found")
    assert AuditLog.objects.filter(makerspace=w.space).count() == before


@pytest.mark.parametrize("role", ["manager", "manual_delegate", "organizer", "coorganizer"])
def test_extras_require_event_opt_in_even_with_event_authority(role):
    from apps.card_designs import extras
    from tests.events.test_scoped_organizer_routes_cx5 import organization_actor
    from tests.events.website_helpers import grantee

    w = world("cc-extras-privacy-" + role)
    actor = w.sm
    if role == "manual_delegate":
        actor, _grant = grantee(w.space, w.event, "edit_details")
    elif role in {"organizer", "coorganizer"}:
        actor = organization_actor(w.event, role)
    extras.write(w.attendee, "event_card", w.card, opted_in=True, blood_group="A+")
    route = routes(w)["extras"]
    views = AuditLog.objects.filter(makerspace=w.space, target_type="events.event",
                                   target_id=str(w.event.pk), action="event_card.extras_viewed")
    EventCardSettings.objects.filter(event=w.event).delete()
    refused(call(actor, route), 404, "not_found")
    setting = EventCardSettings.objects.create(event=w.event, extras_visible_to_organizers=False)
    refused(call(actor, route), 404, "not_found")
    assert views.count() == 0
    setting.extras_visible_to_organizers = True
    setting.save(update_fields=["extras_visible_to_organizers"])
    response = call(actor, route)
    assert response.status_code == 200, response.content
    assert response.json() == [{"card_id": w.card.pk, "name": w.card.printed_name, "blood_group": "A+",
                                "emergency_contact_name": "", "emergency_contact_phone": ""}]
    assert response["Cache-Control"] == "private, no-store"
    assert views.count() == 1
    setting.extras_visible_to_organizers = False
    setting.save(update_fields=["extras_visible_to_organizers"])
    refused(call(actor, route), 404, "not_found")
    assert views.count() == 1
    assert extras.read("event_card", w.card) == {"opted_in": True, "blood_group": "A+",
                                              "emergency_contact_name": "", "emergency_contact_phone": ""}
