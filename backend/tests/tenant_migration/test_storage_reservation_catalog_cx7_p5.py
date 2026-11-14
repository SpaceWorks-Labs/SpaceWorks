"""The new coordination model is classified without creating any User closure edge."""
import pytest
from django.apps import apps

from apps.data_export.guards import validate_all
from apps.data_export.classification import OMITTED_MODELS
from apps.makerspaces.models import StorageQuotaReservation
from apps.tenant_migration.tenant_dump_catalog import validate_catalog
from apps.tenant_rls.scope_registry import predicates

pytestmark = [pytest.mark.django_db, pytest.mark.area_tenant_migration, pytest.mark.area_data_export]


def test_reservation_has_no_identity_edge_and_all_catalog_guards_cover_it():
    assert "makerspaces.StorageQuotaReservation" in OMITTED_MODELS
    assert [field.name for field in StorageQuotaReservation._meta.fields if field.is_relation] == ["makerspace"]
    assert "makerspaces.StorageQuotaReservation" in predicates()
    assert apps.get_model("makerspaces", "StorageQuotaReservation") is StorageQuotaReservation
    validate_all()
    validate_catalog()


def test_reservation_coordination_has_no_control_creator(client):
    from django.contrib import admin
    from tests.accounts.reauth_helpers import force_recent_control_login
    from tests.r2_superadmin_local.helpers import superadmin
    force_recent_control_login(client, superadmin("p5-reservation-root"))
    assert admin.site.is_registered(StorageQuotaReservation) is False
    path = "/control/makerspaces/storagequotareservation/add/"
    assert client.get(path).status_code == 404
    assert client.post(path, {}).status_code == 404
    assert StorageQuotaReservation.objects.count() == 0
