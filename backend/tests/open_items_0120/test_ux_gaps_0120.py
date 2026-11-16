"""UX-pass backend gaps (owner rule 261): server-side labels, exact fix-URLs, offsite reauth."""
import uuid

import pytest
from django.urls import reverse
from django.utils import translation

from apps.accounts.models import User
from apps.audit.models import AuditLog
from tests.backup.offsite_test_support import make_destination
from tests.stage4.helpers import bearer_client

pytestmark = pytest.mark.django_db


def test_deployment_apps_carry_a_translated_label_and_keep_app_label():
    from apps.makerspaces.module_groups import deployment_app_status
    from apps.separability.tombstones import SEPARABLE_APPS
    rows = deployment_app_status()["apps"]
    assert {row["app_label"] for row in rows} == set(SEPARABLE_APPS)
    assert all(row["label"] and row["label"] != row["app_label"] for row in rows)
    assert {row["app_label"]: row["label"] for row in rows}["payments_rail"] == "Online payments"


def test_unlisted_app_label_is_humanised():
    from apps.makerspaces.module_groups import app_display_label
    assert app_display_label("some_new_app") == "Some new app"


def test_app_labels_go_through_gettext(settings):
    from apps.makerspaces import module_groups
    with translation.override("en"):
        assert module_groups.app_display_label("shop") == "Shop"


def test_backup_snapshot_has_status_label_and_keeps_status():
    from apps.operations.platform_signals import backup_snapshot, backup_status_label
    snapshot = backup_snapshot()
    assert snapshot["status"] == "never" and snapshot["status_label"] == "Never run"
    assert backup_status_label("failed") == "Failed"
    assert backup_status_label("odd_value") == "Odd value"


def test_backup_status_label_is_in_the_dashboard_payload():
    from apps.operations.platform_dashboard import build_platform_dashboard
    assert build_platform_dashboard()["backup"]["status_label"]


def test_prize_payout_template_fields_have_label_and_help():
    from apps.payments.event_payouts.template_labels import field_descriptor
    from apps.payments.event_payouts.templates import ROUTING_FIELDS
    for fields in ROUTING_FIELDS.values():
        for key in fields:
            row = field_descriptor(key)
            assert row["key"] == key and row["required"] is True
            assert row["label"] and "_" not in row["label"]
    assert field_descriptor("ifsc")["label"] == "IFSC code" and field_descriptor("ifsc")["help"]
    assert field_descriptor("holder_name")["help"] == ""


def test_fix_urls_point_at_exact_settings_sections():
    from apps.makerspaces.platform import SETTINGS_FIX_PATHS, staff_payment_settings_url
    assert all(path.startswith("settings/") and len(path) > len("settings/") for path in SETTINGS_FIX_PATHS.values())
    url = staff_payment_settings_url(None, outcome="ok")
    assert "/admin/settings/money?" in url and "/admin/settings?" not in url


def _unverified():
    actor = User.objects.create_superuser(username=f"ux-{uuid.uuid4().hex}", password="x")
    return actor, bearer_client(actor)


def test_every_offsite_write_needs_recent_reauth_and_reads_do_not():
    actor, client = _unverified()
    destination = make_destination("cold")
    detail = reverse("admin-backup-destination", args=[destination.pk])
    assert client.get(reverse("admin-backup-destinations")).status_code == 200
    assert client.get(detail).status_code == 200
    writes = [
        client.patch(detail, {"retention_days": 30}, format="json"),
        client.patch(detail, {"name": "renamed"}, format="json"),
        client.post(reverse("admin-backup-destination-probe", args=[destination.pk])),
        client.post(reverse("admin-backup-destination-retire", args=[destination.pk])),
        client.post(reverse("admin-backup-destination-push")),
    ]
    for response in writes:
        assert response.status_code == 403, response.content
        assert response.data["code"] == "recent_reauth_required"
    assert not AuditLog.objects.filter(action__in=(
        "backup.destination_updated", "backup.destination_probed", "backup.destination_retired",
        "backup.offsite_push_requested")).exists()
    assert bearer_client(actor, recent=True).patch(detail, {"name": "renamed"}, format="json").status_code == 200
