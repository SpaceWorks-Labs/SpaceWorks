from tests.events.manual_grant_fixture import create_manual_grant
import pytest
from django.apps import apps
from django.utils import timezone

from apps.accounts.models import User
from apps.data_export.datasets import DATASET_SPECS
from apps.data_export.models import EXPORTED_MODELS, MODELS
from apps.data_export.references import USER_EDGES
from apps.data_export.types import Fidelity, OmittedModel
from apps.events.models import EventStaffGrant, EventStaffGrantInvite
from apps.events.services_staff_grants import create_invite
from apps.makerspaces.lifecycle_purge import purge
from apps.makerspaces.module_install import uninstall_module
from apps.makerspaces.module_purge import purge_module
from apps.makerspaces.models import Makerspace
from apps.separability.registry import purge_plan_for
from apps.tenant_migration.audit_references import AUDIT_TARGET_DISPOSITIONS, AuditReferenceDisposition
from apps.tenant_migration.tenant_dump_catalog import FIELD_POLICIES, validate_catalog
from apps.tenant_migration.tenant_dump_field_snapshot import FIRST_PARTY_FIELD_NAMES
from apps.tenant_migration.tenant_dump_model_catalog import FIRST_PARTY_MODEL_RULES
from apps.tenant_migration.tenant_dump_types import AuthorityDisposition, ModelDisposition
from apps.tenant_migration.unique_values import DEPLOYMENT_GLOBAL_UNIQUE_RULES
from tests.events.staff_grant_helpers import grant_fixture
from tests.events.ticketing_helpers import event_space, open_event

LABELS = ("events.EventStaffGrant", "events.EventStaffGrantInvite")


@pytest.mark.parametrize("label", LABELS)
def test_grant_credentials_have_total_drop_classification_without_datasets(label):
    assert isinstance(MODELS[label], OmittedModel)
    assert label not in EXPORTED_MODELS and label not in DATASET_SPECS
    assert FIRST_PARTY_MODEL_RULES[label].disposition is ModelDisposition.DROP
    actual = {field.name for field in apps.get_model(label)._meta.get_fields() if field.concrete or field.many_to_many}
    assert FIRST_PARTY_FIELD_NAMES[label] == actual
    assert all(FIELD_POLICIES[(label, name)].dispositions == (AuthorityDisposition.DROP,) for name in actual)
    assert not any(edge[0] == label for edge in DEPLOYMENT_GLOBAL_UNIQUE_RULES)
    assert AUDIT_TARGET_DISPOSITIONS[label.lower()].disposition is AuditReferenceDisposition.SOURCE_LOCAL_SNAPSHOT


@pytest.mark.parametrize("label,field", [
    ("events.EventStaffGrant", "user"),
    ("events.EventStaffGrant", "granted_by"),
    ("events.EventStaffGrant", "revoked_by"),
    ("events.EventStaffGrantInvite", "created_by"),
    ("events.EventStaffGrantInvite", "redeemed_by"),
])
def test_all_user_references_are_excluded_from_both_fidelity_closures(label, field):
    for fidelity in Fidelity:
        edge = USER_EDGES[(fidelity, label, field)]
        assert not edge.included and not edge.raw
        assert "reissue" in edge.reason


def test_full_literal_catalog_matches_live_runtime_models():
    validate_catalog()


@pytest.mark.django_db(transaction=True)
def test_events_module_purge_deletes_only_its_tenant_grant_credentials():
    space, manager, user, event, grant = grant_fixture()
    invite, _ = create_invite(event, actor=manager, permissions=["check_in"])
    other = event_space("grants-retained")
    foreign = open_event(other)
    foreign_grant = create_manual_grant(
        makerspace=other, event=foreign, user=user, granted_by=manager, permissions=["check_in"],
    )
    root = User.objects.create_superuser(username="grants-purge-root", email="root@example.test", password="pw")
    uninstall_module(space, "events")
    assert EventStaffGrant.objects.filter(pk=grant.pk).exists()
    assert EventStaffGrantInvite.objects.filter(pk=invite.pk).exists()
    assert purge_plan_for("events") is not None
    result = purge_module(space, "events", root)
    assert result["event_staff_grants"] == 1 and result["event_staff_grant_invites"] == 1
    assert not EventStaffGrant.objects.filter(pk=grant.pk).exists()
    assert not EventStaffGrantInvite.objects.filter(pk=invite.pk).exists()
    assert EventStaffGrant.objects.filter(pk=foreign_grant.pk).exists()
    assert Makerspace.objects.filter(pk=space.pk).exists()


@pytest.mark.django_db(transaction=True)
def test_whole_tenant_purge_removes_both_grant_models():
    space, manager, _, event, grant = grant_fixture()
    invite, _ = create_invite(event, actor=manager, permissions=["check_in"])
    root = User.objects.create_superuser(username="tenant-grants-purge-root", email="root@example.test", password="pw")
    space.archived_at = timezone.now()
    space.save(update_fields=["archived_at"])
    purge(space, root)
    assert not EventStaffGrant.objects.filter(pk=grant.pk).exists()
    assert not EventStaffGrantInvite.objects.filter(pk=invite.pk).exists()
