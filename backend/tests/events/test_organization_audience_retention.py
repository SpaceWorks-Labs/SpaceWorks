"""Inert portable admission, complete catalog, independent backup and purge scope."""

import pytest
from django.utils import timezone

from apps.accounts.models import User
from apps.events import services
from apps.events.models import Event, EventOrganizer, EventSeries
from apps.events.organization_audience import AUDIENCE, OrganizationAudienceRefused, require_organization_audience
from apps.makerspaces.lifecycle_purge import purge
from apps.makerspaces.module_install import uninstall_module
from apps.makerspaces.module_purge import purge_module
from apps.organizations.models import Organization, OrganizationMakerspace
from apps.tenant_migration.row_planning import _apply_target_fields
from apps.tenant_migration.tenant_dump_catalog import validate_catalog
from tests.tenant_migration.object_helpers import memory_objects
from tests.events.organization_audience_helpers import audience_fixture, direct
from tests.events.ticketing_helpers import event_space, open_event

pytestmark = pytest.mark.django_db(transaction=True)


def test_runtime_catalog_and_all_audience_columns():
    validate_catalog()
    from apps.events.models import EventRegistration
    from apps.makerspaces.models import Makerspace
    for model, name in ((Event, "registration_audience"), (EventSeries, "registration_audience"),
                        (EventRegistration, "registration_audience"), (Makerspace, "event_default_registration_audience")):
        field = model._meta.get_field(name)
        assert field.max_length >= len(AUDIENCE)
        assert AUDIENCE in dict(field.choices)


@pytest.mark.parametrize("label", ["events.Event", "events.EventSeries"])
def test_real_target_projection_always_blocks_source_readiness(label):
    source = {"registration_audience": AUDIENCE, "organization_admission_blocked": False}
    target_row = dict(source)
    _apply_target_fields(label, source, target_row)
    assert target_row["registration_audience"] == AUDIENCE
    assert target_row["organization_admission_blocked"] is True


def test_portable_event_with_unrelated_target_owner_remains_blocked_until_explicit_review():
    venue, orgs, _, event, manager = audience_fixture()
    user = direct(orgs[2])
    source = {"registration_audience": event.registration_audience, "organization_admission_blocked": False}
    row = dict(source); _apply_target_fields("events.Event", source, row)
    Event.objects.filter(pk=event.pk).update(**row)
    event.refresh_from_db()
    with pytest.raises(OrganizationAudienceRefused) as error:
        require_organization_audience(event, user)
    assert str(error.value.detail["code"]) == "organization_audience_not_ready"
    services.update_event(event, actor=manager, description="Ordinary detail edit")
    event.refresh_from_db(); assert event.organization_admission_blocked
    event = services.update_event(event, actor=manager, registration_audience=AUDIENCE)
    assert not event.organization_admission_blocked
    require_organization_audience(event, user)


def test_real_portable_archive_materialization_blocks_new_target_owner(memory_objects):
    from apps.makerspaces.models import Makerspace
    from apps.tenant_migration.materialization import materialize_tenant
    from tests.data_export.portable_helpers import make_space, make_user
    from tests.encryption.conftest import enabled_encryption
    from tests.tenant_migration.materialization_helpers import portable_import_case

    def prepare(source, user, request):
        source.events.update(registration_audience=AUDIENCE)
        for event in source.events.all():
            event.registrations.update(registration_audience=AUDIENCE)
        return None

    with enabled_encryption():
        source_user = make_user("org-archive")
        source = make_space("org-archive")
        with portable_import_case(source, source_user, prepare_source=prepare) as case:
            case.decide_walk_in(source_user)
            result = materialize_tenant(case.root, case.job, case.carried,
                target_identity={"name": "Imported organizations", "slug": "org-import"}, batch_size=2)
        target = Makerspace.objects.get(pk=result.target_makerspace_id)
        # Materialization deliberately leaves the tenant IMPORTING. This test is
        # about audience readiness after cutover, not the independent lifecycle gate.
        from apps.tenant_migration.target_state import ACTIVE, IMPORTING, transition_target
        assert transition_target(target.pk, IMPORTING, ACTIVE) == 1
        # Cutover also has the operator reopen the tenant-import PII write fence
        # (`open_pii_write_fence`); protected event writes stay refused until then.
        from apps.encryption.models import PiiMakerspaceWriteFence
        from apps.encryption.write_fence import reopen
        root = User.objects.create_superuser(username="target-reviewer", password="pw")
        reopen(PiiMakerspaceWriteFence.objects.get(makerspace=target).operation_id, root.pk)
        target.refresh_from_db()
        target.enabled_modules += ["events"]
        target.enabled_features += ["events.organization_audience"]
        target.save(update_fields=["enabled_modules", "enabled_features"])
        target_owner = Organization.objects.create(name="Unrelated target owner", slug="target-owner")
        OrganizationMakerspace.objects.create(organization=target_owner, makerspace=target, relationship="owner")
        target_member = direct(target_owner, "target-member")
        event = target.events.get()
        assert event.registration_audience == AUDIENCE and event.organization_admission_blocked
        assert event.registrations.get().registration_audience == AUDIENCE
        assert not event.organizers.exists()
        with pytest.raises(OrganizationAudienceRefused) as failure:
            require_organization_audience(event, target_member)
        assert str(failure.value.detail["code"]) == "organization_audience_not_ready"
        event = services.update_event(event, actor=root, registration_audience=AUDIENCE)
        require_organization_audience(event, target_member)


def test_deployment_model_roundtrip_preserves_readiness_and_global_organization_graph():
    from django.core import serializers
    _, orgs, _, event, _ = audience_fixture()
    graph = [event, *orgs, *OrganizationMakerspace.objects.all(), *EventOrganizer.objects.filter(event=event)]
    restored = [entry.object for entry in serializers.deserialize("json", serializers.serialize("json", graph))]
    restored_event = next(row for row in restored if isinstance(row, Event))
    assert restored_event.registration_audience == AUDIENCE
    assert restored_event.organization_admission_blocked == event.organization_admission_blocked
    assert sum(isinstance(row, OrganizationMakerspace) for row in restored) == 3


@pytest.mark.parametrize("whole_tenant", [False, True])
def test_local_purge_does_not_delete_global_orgs_memberships_or_foreign_organizers(whole_tenant):
    venue, orgs, _, event, _ = audience_fixture()
    participant = direct(orgs[0])
    foreign_space = event_space("foreign-host")
    foreign_event = open_event(foreign_space)
    link = EventOrganizer.objects.create(event=foreign_event, organization=orgs[2])
    root = User.objects.create_superuser(username="org-purge-root", password="pw")
    if whole_tenant:
        venue.archived_at = timezone.now(); venue.save(update_fields=["archived_at"])
        purge(venue, root)
    else:
        uninstall_module(venue, "events")
        purge_module(venue, "events", root)
    assert Organization.objects.filter(pk__in=[row.pk for row in orgs]).count() == 3
    assert participant.organization_memberships.exists()
    assert EventOrganizer.objects.filter(pk=link.pk).exists()
    assert not Event.objects.filter(pk=event.pk).exists()
