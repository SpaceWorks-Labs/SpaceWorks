"""Artifact-approved key reissuance must refuse before preparing a credential file."""
import uuid

import pytest
from django.db import connection
from rest_framework.exceptions import APIException

from apps.apiclients.models import ApiClient, ApiClientImportApproval
from apps.audit.models import AuditLog
from apps.tenant_migration.host_credential_delivery import CredentialDeliveryStore
from apps.tenant_migration.tenant_restore_api_clients import reissue_approved_client
from tests.limits_0120.creator_races_cx7 import race_creators
from tests.return_helpers import make_space
from tests.tenant_migration.test_api_client_contract_d8 import _approval, _catalog, _catalog_entry, _parse

pytestmark = [pytest.mark.django_db, pytest.mark.area_auth, pytest.mark.area_tenant_migration]


def world(settings, tmp_path):
    settings.MANAGED_PLANS_ENABLED = False
    space = make_space("p4a-import-keys")
    space.resource_limit_overrides = {"api_clients": 1}
    space.save(update_fields=["resource_limit_overrides"])
    records = []
    for index in range(2):
        capture = uuid.uuid4()
        catalog = _catalog(_catalog_entry(source_client_ref=str(index + 1) * 64, label=f"Key {index}"))
        record = _approval(catalog, capture_id=capture, nonce=f"p4a-nonce-{index}")
        records.append(_parse(catalog, [record], capture)[0])
    return space, records, CredentialDeliveryStore(tmp_path, require_root_owned=False)


def files(path):
    return {str(file.relative_to(path)): file.read_bytes() for file in path.rglob("*") if file.is_file()}


def snapshot():
    return {model.__name__: list(model.objects.order_by("pk").values())
            for model in (ApiClient, ApiClientImportApproval, AuditLog)}


def test_import_reissue_max_next_refusal_keeps_database_and_host_delivery_untouched(settings, tmp_path):
    space, records, store = world(settings, tmp_path)
    first = reissue_approved_client(makerspace=space, record=records[0], delivery_store=store)
    assert ApiClient.objects.filter(makerspace=space, is_active=True).count() == 1
    before, prepared = snapshot(), files(tmp_path)
    assert reissue_approved_client(makerspace=space, record=records[0], delivery_store=store).pk == first.pk
    assert snapshot() == before
    assert files(tmp_path) == prepared
    with pytest.raises(APIException) as raised:
        reissue_approved_client(makerspace=space, record=records[1], delivery_store=store)
    assert (raised.value.status_code, str(raised.value.detail["code"])) == (400, "limit_reached")
    assert snapshot() == before
    assert files(tmp_path) == prepared


@pytest.mark.django_db(transaction=True)
def test_import_key_creators_racing_at_last_slot_prepare_only_the_winner(settings, tmp_path):
    if connection.vendor != "postgresql":
        pytest.skip("Requires PostgreSQL row locks")
    space, records, store = world(settings, tmp_path)
    assert race_creators(lambda index: reissue_approved_client(
        makerspace=space, record=records[index], delivery_store=store)) == [
            (201, "created"), (400, "limit_reached")]
    assert ApiClient.objects.filter(makerspace=space, is_active=True).count() == 1
    assert ApiClientImportApproval.objects.filter(makerspace=space).count() == 1
    client = ApiClient.objects.get(makerspace=space)
    prepared = files(tmp_path)
    assert set(prepared) == {f"{client.import_provenance_digest}.secret.json"}
