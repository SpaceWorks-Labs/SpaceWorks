"""Fixtures for the RP-5 repairs report family. Local only (never committed)."""

from datetime import timedelta
from uuid import uuid4

from django.utils import timezone

from apps.maintenance.models import IssueReport, WorkOrder
from apps.maintenance.repairs import services_issues as svc
from tests.maintenance.l16_helpers import world as l16_world
from tests.return_helpers import authenticated_client, make_member

KEYS = ("repairs-work-orders", "repairs-technician-workload", "repairs-time-by-area", "repairs-parts-used")
REPAIRS_SWITCHES = ("machines.repairs", "inventory.repairs", "bookings.room_repairs")
MAINTENANCE_SWITCHES = ("machines.maintenance", "inventory.maintenance", "bookings.room_maintenance")


def world(slug):
    w = l16_world(slug)
    w.space.enabled_modules = sorted(set(w.space.enabled_modules or []) | {"reports"})
    w.space.save(update_fields=["enabled_modules"])
    return w


def role(w, slug):
    return make_member(f"rp5-{slug}-{uuid4().hex[:6]}", w.space, membership_role=slug)


def machine_manager(w, machine_type):
    from apps.machines.models_membership_scope import MembershipMachineTypeScope
    from apps.makerspaces.models import MakerspaceMembership
    user = role(w, "machine_manager")
    membership = MakerspaceMembership.staff_tracks.get(user=user, makerspace=w.space)
    MembershipMachineTypeScope.objects.create(membership=membership, machine_type=machine_type)
    return user


def issue(w, subject_type, subject, title="Broken", *, contact=None):
    row = svc.open_issue(w.manager, w.space, subject_type=subject_type, subject=subject, title=title)
    if contact is not None:
        row = svc.assign(w.manager, row, contact=contact)
    return IssueReport.objects.get(pk=row.pk)


def set_issue(row, **fields):
    IssueReport.objects.filter(pk=row.pk).update(**fields)
    row.refresh_from_db()
    return row


def set_due(row, days):
    WorkOrder.objects.filter(pk=row.work_order_id).update(due_on=timezone.localdate() + timedelta(days=days))


def hours_ago(hours):
    return timezone.now() - timedelta(hours=hours)


def client(user):
    return authenticated_client(user)


def analytics(user, w, key):
    return client(user).get(f"/api/v1/admin/makerspace/{w.space.pk}/analytics/{key}")


def catalog_keys(user, w):
    response = client(user).get(f"/api/v1/admin/makerspace/{w.space.pk}/reports/catalog")
    assert response.status_code == 200, response.content
    return {row["key"]: row for row in response.json()["results"] if row["key"] in KEYS}


def export_body(response):
    return b"".join(response.streaming_content if response.streaming else [response.content]).decode()
