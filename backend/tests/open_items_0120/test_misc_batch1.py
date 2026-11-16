"""Open items A25, A28, A37, A42, A43, A45, A46, B12, C26, C29 (batch 1)."""
from datetime import timedelta

import pytest
from django.utils import timezone

from tests.fixed_roles.helpers import staff_account
from tests.maintenance.l16_helpers import world
from tests.return_helpers import authenticated_client, make_issued_request, make_member

pytestmark = pytest.mark.django_db


def test_a28_combined_calendar_carries_own_loan_due_only():
    from apps.events.calendar_feed_combined import render_combined_calendar
    w = world("oi-a28")
    request = make_issued_request(w.space, w.manager, [(w.product, 1)])
    request.return_due_at = timezone.now() + timedelta(days=3)
    request.save(update_fields=["return_due_at"])
    ics = render_combined_calendar(w.space, request.requester).decode()
    assert f"loan-due-{request.pk}@spaceworks" in ics
    other = make_member("oi-a28-other", w.space)
    assert f"loan-due-{request.pk}@spaceworks" not in render_combined_calendar(w.space, other).decode()


def test_a37_link_change_webhooks_are_in_the_catalogue_and_wired():
    from apps.integrations.link_webhooks import link_webhook
    from apps.integrations.models import NotificationFeature as F
    from apps.integrations.notification_catalog import FEATURE_EVENTS
    assert {"event_booking_linked", "event_loan_linked", "event_loan_unlinked"} <= set(FEATURE_EVENTS[F.EVENTS])
    assert {"booking_loan_linked", "booking_loan_unlinked"} <= set(FEATURE_EVENTS[F.BOOKINGS])
    assert callable(link_webhook)


def test_a43_four_member_events_have_reviewed_addressed_projections():
    from apps.integrations.messaging.projections import PROJECTION_KEYS, render_sms
    for key in (("hardware_requests", "renewed", "member"), ("hardware_requests", "pickup_expiring", "member"),
                ("hardware_requests", "repair_closed", "member"), ("payments", "shop_order_collected", "member")):
        assert key in PROJECTION_KEYS
        assert set(PROJECTION_KEYS[key]) <= {"makerspace.name", "request.id"}  # ids only, never a body
    text = render_sms("hardware_requests", "renewed", "member", {"makerspace.name": "Acme", "request.id": 3})
    assert "Acme" in text


def test_a42_platform_credential_fallbacks_are_not_gated_on_the_hosting_switch():
    import pathlib
    apps = pathlib.Path(__file__).resolve().parents[2] / "apps"
    for rel in ("integrations/messaging", "integrations/notification_sender.py", "analytics",
                "makerspaces/telemetry_public.py", "card_designs/wallet"):
        target = apps / rel
        for path in ([target] if target.is_file() else target.rglob("*.py")):
            assert "hosts_other_spaces" not in path.read_text(encoding="utf-8"), path  # decision 240


def test_a45_included_hours_rows_cascade_with_their_booking_and_have_no_immutability_trigger():
    from django.db import connection
    from apps.bookings.models_included_hours import IncludedHoursUsage
    with connection.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid "
                       "WHERE c.relname = 'bookings_includedhoursusage' AND NOT t.tgisinternal")
        assert cursor.fetchone()[0] == 0
    for field in ("makerspace", "term", "booking", "reverses"):
        assert IncludedHoursUsage._meta.get_field(field).remote_field.on_delete.__name__ == "CASCADE"


def test_a46_only_the_known_guarded_fk_may_be_set_null_on_exact_row_tables():
    """Pin: a new nullable SET_NULL FK on an immutable snapshot table would be blocked on a space restore until
    `space_restore_exact_rows.null_reference` learns it, so adding one must fail here first."""
    from django.apps import apps
    from django.db import models
    from apps.backup.space_restore_exact_rows import EXACT_ROW_TABLES
    found = []
    for model in apps.get_models():
        if model._meta.db_table not in EXACT_ROW_TABLES:
            continue
        for field in model._meta.concrete_fields:
            if field.is_relation and field.remote_field.on_delete is models.SET_NULL and field.null:
                found.append((model._meta.db_table, field.name))
    # `creator` is a user FK on the retained decision (nulled when the author's account is erased, see
    # accounts/booking_decision_deletion.py); only `booking` needs the restore-time guarded detach.
    assert found == [("events_eventbookingdecision", "booking"), ("events_eventbookingdecision", "creator")]


def test_b12_the_waiver_gate_can_outlive_guest_passes():
    from apps.makerspaces.guest_pass_queries import require_waiver
    from apps.makerspaces.models import GuestPassPolicy, MakerspaceWaiver
    from apps.presence.guard import WaiverAcceptanceRequired
    from tests.makerspaces.test_guest_passes import _space
    space = _space("oi-b12")
    space.enabled_features = [f for f in (space.enabled_features or []) if f != "membership.guest_passes"]
    space.save(update_fields=["enabled_features"])
    MakerspaceWaiver.objects.create(makerspace=space, version="v1", body="Sign", is_active=True)
    user = make_member("oi-b12-guest", space)
    require_waiver(user, space, None)  # passes off and no flag: pre-0.12 behaviour
    GuestPassPolicy.objects.update_or_create(makerspace=space, defaults={"waiver_gate_without_passes": True})
    with pytest.raises(WaiverAcceptanceRequired):
        require_waiver(user, space, None)


def test_c26_staff_read_of_a_members_included_hours_is_scoped():
    w = world("oi-c26")
    boss = staff_account(w.space, "oi-c26-boss", "space_manager")
    from tests.l3_local.helpers import member as community_member  # decision 63: a member is a community account
    member = community_member(w.space, "oi-c26-member")[0]
    url = f"/api/v1/admin/makerspace/{w.space.pk}/members/{member.pk}/included-hours"
    data = authenticated_client(boss).get(url).json()
    assert data["member_id"] == member.pk and isinstance(data["pools"], list)
    stranger = community_member(w.space, "oi-c26-stranger")[0]
    assert authenticated_client(stranger).get(url).status_code in (403, 404)
    other = world("oi-c26-other")
    assert authenticated_client(boss).get(
        f"/api/v1/admin/makerspace/{other.space.pk}/members/{member.pk}/included-hours").status_code == 404


def test_a25_organizer_attendance_counts_only_events_the_actors_organizations_run():
    from apps.events.models import Event, EventOrganizer, EventRegistration
    from apps.organizations.models import Organization, OrganizationMembership
    w = world("oi-a25")
    org = Organization.objects.create(name="Partner Org", slug="partner-org-a25")
    person = make_member("oi-a25-org", w.space)
    OrganizationMembership.objects.create(organization=org, user=person, status="active",
                                          granted_actions=["manage_events"])
    start = timezone.now()
    end = start + timedelta(hours=1)
    mine = Event.objects.create(makerspace=w.space, title="Ours", starts_at=start, ends_at=end)
    Event.objects.create(makerspace=w.space, title="Theirs", starts_at=start, ends_at=end)
    EventOrganizer.objects.create(event=mine, organization=org)
    EventRegistration.objects.create(event=mine, member=person, name="P", email="p@example.test", phone="1",
                                     status="attended")
    data = authenticated_client(person).get("/api/v1/admin/organized-events/attendance/").json()
    assert [row["event_id"] for row in data["results"]] == [mine.pk]
    assert data["totals"]["attended"] == 1


def test_c29_shop_notices_stay_under_payments_but_display_as_shop():
    from apps.notifications.inbox_families import display_family
    assert display_family("payments", "shop_order_new") == "shop"
    assert display_family("payments", "payment_received") == "payments"
    assert display_family("maintenance", "incident_reported") == "safety"
