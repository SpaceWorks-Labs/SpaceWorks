"""Module-off detail contracts; pending actual execution."""
import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.makerspaces.models import MakerspaceMembership
from apps.operations.models import QrPrintBatch, StockTransfer
from tests.modules.family_helpers import family_space

pytestmark = pytest.mark.django_db


def manager(space, name):
    user = User.objects.create_user(username=name, email=f"{name}@example.test", display_name=name,
                                    access_status=User.AccessStatus.ACTIVE)
    MakerspaceMembership.staff_tracks.create(user=user, makerspace=space, track="staff", status="active",
                                        role=MakerspaceMembership.Role.SPACE_MANAGER,
                                        assigned_role=space.roles.get(slug="space_manager"))
    return user


def api(user):
    result = APIClient()
    result.force_authenticate(user)
    return result


def test_qr_batch_detail_off_then_on_and_outside_scope():
    space = family_space("qr-detail-off")
    actor = manager(space, "qr-detail-manager")
    other = manager(family_space("qr-detail-other", "qr_print_batches"), "qr-detail-outsider")
    batch = QrPrintBatch.objects.create(makerspace=space, title="Batch", created_by=actor)
    url = reverse("qr-print-batch-detail", args=[batch.pk])
    denied = api(actor).get(url)
    assert denied.status_code == 404 and denied.data["module"] == "qr_print_batches"
    assert api(other).get(url).status_code == 404
    space.enabled_modules = [*space.enabled_modules, "qr_print_batches"]
    space.save(update_fields=["enabled_modules"])
    assert api(actor).get(url).status_code == 200


def test_transfer_requires_enabled_visible_endpoint():
    source = family_space("transfer-source", "stock_transfers")
    destination = family_space("transfer-destination")
    source_actor = manager(source, "transfer-source-manager")
    destination_actor = manager(destination, "transfer-destination-manager")
    outsider = manager(family_space("transfer-outsider", "stock_transfers"), "transfer-outsider-manager")
    transfer = StockTransfer.objects.create(makerspace=source, source_makerspace=source,
                                            destination_makerspace=destination, reason="Move")
    url = reverse("stock-transfer-detail", args=[transfer.pk])
    denied = api(destination_actor).get(url)
    assert denied.status_code == 404 and denied.data["module"] == "stock_transfers"
    assert api(outsider).get(url).status_code == 404
    assert api(source_actor).get(url).status_code == 200
    destination.enabled_modules = [*destination.enabled_modules, "stock_transfers"]
    destination.save(update_fields=["enabled_modules"])
    source.enabled_modules = [key for key in source.enabled_modules if key != "stock_transfers"]
    source.save(update_fields=["enabled_modules"])
    assert api(destination_actor).get(url).status_code == 200
    denied = api(source_actor).get(url)
    assert denied.status_code == 404 and denied.data["module"] == "stock_transfers"


def test_historical_transfer_without_endpoints_preserves_superadmin_owner_gate():
    space = family_space("historic-transfer", "stock_transfers")
    root = User.objects.create_superuser(username="historical-transfer-root", email="root@example.test",
        display_name="Platform", role=User.Role.SUPERADMIN, is_staff=True, is_superuser=True,
        access_status=User.AccessStatus.ACTIVE)
    manager_actor = manager(space, "historical-transfer-manager")
    transfer = StockTransfer.objects.create(makerspace=space, reason="Historical")
    assert transfer.source_makerspace_id is None and transfer.destination_makerspace_id is None
    url = reverse("stock-transfer-detail", args=[transfer.pk])
    assert api(root).get(url).status_code == 200
    # The fallback does not widen the existing endpoint-scoped queryset for non-superusers.
    assert api(manager_actor).get(url).status_code == 404
    space.enabled_modules = [key for key in space.enabled_modules if key != "stock_transfers"]
    space.save(update_fields=["enabled_modules"])
    denied = api(root).get(url)
    assert denied.status_code == 404 and denied.data["module"] == "stock_transfers"
    assert api(manager_actor).get(url).status_code == 404
