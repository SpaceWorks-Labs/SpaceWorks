"""R4 audit B: audit-log coverage fixes (PRD section 11)."""

from types import SimpleNamespace

import pytest
from django.contrib.admin.models import CHANGE, DELETION, LogEntry
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse

from apps.audit import presentation
from apps.audit.models import AuditLog
from apps.audit.presentation_catalog import UNRECOGNIZED_LABEL
from apps.audit.presentation_guards import presentation_catalog_errors
from apps.boxes.models import QrCode
from apps.inventory.models import InventoryAsset, TrackingMode
from apps.notifications.models import Notification
from tests.return_helpers import authenticated_client, make_member, make_product, make_space

pytestmark = pytest.mark.django_db


def _row(action, meta):
    return SimpleNamespace(action=action, meta=meta)


@pytest.mark.parametrize("action, label", [
    ("booking.created", "Booking created"),
    ("event.registration_approved", "Event registration approved"),
    ("auth.login_succeeded", "Auth login succeeded"),
    ("member.phone_verified", "Member phone verified"),
    ("events.answers.locked", "Events answers locked"),
    ("event.programme.judge_pulled_project", "Event programme judge pulled project"),
])
def test_reviewed_wrapper_actions_read_as_words_and_keep_meta_withheld(action, label):
    projection = presentation.project(_row(action, {"email": "x@example.test"}))
    assert projection.action_label == label
    assert projection.meta == {} and projection.meta_redacted is True


def test_an_unreviewed_action_is_still_unrecognized():
    assert presentation.action_label("never.heard_of") == UNRECOGNIZED_LABEL
    assert presentation.action_label("") == UNRECOGNIZED_LABEL


def test_the_catalogue_guard_still_holds():
    assert presentation_catalog_errors() == []


def test_creating_an_asset_qr_is_audited_once():
    space = make_space("r4-asset-qr")
    manager = make_member("r4-asset-qr-manager", space)
    product = make_product(space, tracking_mode=TrackingMode.INDIVIDUAL)
    asset = InventoryAsset.objects.create(makerspace=space, product=product, asset_tag="R4-1")
    client = authenticated_client(manager)
    assert client.post(f"/api/v1/admin/assets/{asset.id}/qr", {}, format="json").status_code == 201
    assert client.post(f"/api/v1/admin/assets/{asset.id}/qr", {}, format="json").status_code == 201
    qr = QrCode.objects.get(target_type=QrCode.TargetType.ASSET, target_id=asset.id)
    rows = AuditLog.objects.filter(action="qr.asset_created")
    assert rows.count() == 1 and rows.get().target_id == str(qr.pk)
    assert presentation.action_label("qr.asset_created") == "Asset QR code created"


def test_legacy_mark_read_routes_are_audited():
    space = make_space("r4-mark-read")
    space.enabled_modules = sorted({*space.enabled_modules, "notifications"})
    space.save(update_fields=["enabled_modules"])
    manager = make_member("r4-mark-read-manager", space)
    first = Notification.objects.create(makerspace=space, title="One")
    Notification.objects.create(makerspace=space, title="Two")
    client = authenticated_client(manager)
    read = client.post(reverse("notifications:notifications-read", args=[space.pk, first.pk]))
    assert read.status_code == 200, read.data
    assert AuditLog.objects.filter(action="notification.read", target_id=str(first.pk)).count() == 1
    assert client.post(reverse("notifications:notifications-read", args=[space.pk, first.pk])).status_code == 200
    assert AuditLog.objects.filter(action="notification.read").count() == 1  # already read: no change, no row
    every = client.post(reverse("notifications:notifications-read-all", args=[space.pk]))
    assert every.data == {"updated": 1}
    assert AuditLog.objects.get(action="notification.read_all").meta["updated"] == 1


def test_control_form_edits_write_an_audit_row_with_field_names_only():
    from apps.accounts.models import User

    root = User.objects.create_superuser("r4-control-root", email="root@example.test")
    person = User.objects.create_user("r4-control-person", email="person@example.test")
    content_type = ContentType.objects.get_for_model(User)
    LogEntry.objects.log_actions(root.pk, [person], CHANGE, '[{"changed": {"fields": ["Staff status"]}}]',
                                 single_object=True)
    row = AuditLog.objects.get(action="control.object_changed")
    assert row.actor_id == root.pk and row.target_id == str(person.pk)
    assert row.meta == {"via": "control", "model": "accounts.user", "changed_fields": ["Staff status"]}
    assert "person@example.test" not in str(row.meta)
    LogEntry.objects.log_actions(root.pk, [person], DELETION, single_object=True)
    assert AuditLog.objects.get(action="control.object_deleted").makerspace_id is None
    assert content_type.model == "user"


def test_control_bulk_delete_is_audited(client):
    from apps.accounts.models import User
    from apps.inventory.models import Category
    from tests.accounts.reauth_helpers import force_recent_control_login

    root = User.objects.create_superuser("r4-bulk-root", email="bulk@example.test")
    space = make_space("r4-bulk-delete")
    rows = [Category.objects.create(makerspace=space, name=f"R4 {n}", slug=f"r4-{n}") for n in range(2)]
    force_recent_control_login(client, root)
    url = reverse("admin:inventory_category_changelist")
    response = client.post(url, {"action": "delete_selected", "post": "yes",
                                 "_selected_action": [str(row.pk) for row in rows]},
                           HTTP_HOST="localhost", REMOTE_ADDR="127.0.0.1")
    assert response.status_code in (200, 302)
    assert not Category.objects.filter(pk__in=[row.pk for row in rows]).exists()
    row = AuditLog.objects.get(action="control.objects_deleted")
    assert row.meta == {"via": "control", "model": "inventory.category", "count": 2}


def test_the_real_admin_log_methods_reach_the_audit_hook():
    from django.contrib import admin
    from django.test import RequestFactory

    from apps.accounts.models import User
    from apps.inventory.models import Category

    root = User.objects.create_superuser("r4-log-root", email="logroot@example.test")
    space = make_space("r4-log-path")
    row = Category.objects.create(makerspace=space, name="R4 log")
    request = RequestFactory().post("/control/")
    request.user = root
    model_admin = admin.site._registry[Category]
    model_admin.log_change(request, row, [{"changed": {"fields": ["Name"]}}])
    model_admin.log_addition(request, row, [{"added": {}}])
    changed = AuditLog.objects.get(action="control.object_changed")
    assert changed.makerspace_id == space.pk and changed.meta["changed_fields"] == ["Name"]
    assert AuditLog.objects.filter(action="control.object_added", makerspace=space).count() == 1
