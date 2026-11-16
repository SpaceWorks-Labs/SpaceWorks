"""Bulk link deletion fences every parent before invoking per-link services."""

import pytest
from django.contrib.admin import AdminSite
from django.db import connection
from django.test import RequestFactory

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.organizations import admin_links
from apps.organizations.models import OrganizationMakerspace
from apps.tenant_migration.gate_errors import SourceMigrationGateClosed
from apps.tenant_migration.gate_locks import SOURCE_GATE_LOCK_NAMESPACE
from tests.events.organization_audience_helpers import audience_fixture
from tests.events.ticketing_helpers import event_space
from tests.tenant_migration.source_gate_helpers import close_gate

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.mark.parametrize("relationship", ["affiliate", "manager"])
@pytest.mark.parametrize("duplicate_space", [False, True])
def test_bulk_delete_locks_all_organizations_in_pk_order_before_first_change_link(
    monkeypatch, relationship, duplicate_space,
):
    _, orgs, _, _, _ = audience_fixture()
    spaces = [event_space("bulk-first"), event_space("bulk-second")]
    links = [OrganizationMakerspace.objects.create(
        organization=org, makerspace=space, relationship=relationship,
    ) for org, space in zip(reversed(orgs[:2]), spaces)]
    # The existing makerspace sort encounters organization B before A.
    assert links[0].organization_id > links[1].organization_id
    if duplicate_space:
        links.append(OrganizationMakerspace.objects.create(
            organization=orgs[2], makerspace=spaces[0], relationship=relationship,
        ))
    links.sort(key=lambda row: (row.makerspace_id, row.organization_id))
    root = User.objects.create_superuser(username="bulk-link-admin", password="pw")
    request = RequestFactory().post("/control/")
    request.user = root
    model_admin = admin_links.OrganizationMakerspaceAdmin(OrganizationMakerspace, AdminSite())
    locks, gates, calls = [], [], []
    expected_gates = [(SOURCE_GATE_LOCK_NAMESPACE, space.pk) for space in spaces]
    original_change_link = admin_links.change_link

    def observe_locks(execute, sql, params, many, context):
        if "pg_advisory_xact_lock_shared" in sql:
            gates.append(tuple(params))
        if sql.lstrip().startswith("SELECT") and "FOR UPDATE" in sql:
            # Both real advisory locks must be acquired before the first root lock.
            assert gates[:len(expected_gates)] == expected_gates
            locks.append((sql, params))
        return execute(sql, params, many, context)

    def checked_change_link(actor, organization_id, makerspace_id):
        if not calls:
            # These evaluated, sorted bulk locks must precede the first service call.
            assert len(locks) == 2
            # Each tenant is fenced exactly once by the bulk preflight.
            assert gates == expected_gates
            space_sql, space_params = locks[0]
            org_sql, org_params = locks[1]
            assert 'FROM "makerspaces_makerspace"' in space_sql
            assert 'ORDER BY "makerspaces_makerspace"."id" ASC' in space_sql
            assert set(space_params) == {space.pk for space in spaces}
            assert 'FROM "organizations_organization"' in org_sql
            assert 'ORDER BY "organizations_organization"."id" ASC' in org_sql
            assert set(org_params) == {row.organization_id for row in links}
        calls.append((organization_id, makerspace_id))
        return original_change_link(actor, organization_id, makerspace_id)

    monkeypatch.setattr(admin_links, "change_link", checked_change_link)
    selected = OrganizationMakerspace.objects.filter(pk__in=[row.pk for row in links])
    with connection.execute_wrapper(observe_locks):
        model_admin.delete_queryset(request, selected)
    assert calls == [(row.organization_id, row.makerspace_id) for row in links]
    assert not selected.exists()
    assert OrganizationMakerspace.objects.filter(relationship="owner").count() == 3
    entries = AuditLog.objects.filter(action="organization.link_deleted")
    assert entries.count() == len(links)
    assert set(entries.values_list("makerspace_id", flat=True)) == {space.pk for space in spaces}


@pytest.mark.parametrize("frozen_index", [0, 1])
def test_bulk_delete_refuses_a_frozen_tenant_before_any_root_lock_or_deletion(frozen_index):
    _, orgs, _, _, _ = audience_fixture()
    spaces = [event_space("bulk-open"), event_space("bulk-frozen")]
    links = [OrganizationMakerspace.objects.create(
        organization=org, makerspace=space, relationship="affiliate",
    ) for org, space in zip(orgs[:2], spaces)]
    root = User.objects.create_superuser(username="frozen-bulk-admin", password="pw")
    close_gate(spaces[frozen_index], root)
    request = RequestFactory().post("/control/")
    request.user = root
    model_admin = admin_links.OrganizationMakerspaceAdmin(OrganizationMakerspace, AdminSite())
    selected = OrganizationMakerspace.objects.filter(pk__in=[row.pk for row in links])
    row_locks = []

    def observe_locks(execute, sql, params, many, context):
        if "FOR UPDATE" in sql:
            row_locks.append(sql)
        return execute(sql, params, many, context)

    with connection.execute_wrapper(observe_locks), pytest.raises(SourceMigrationGateClosed):
        model_admin.delete_queryset(request, selected)
    assert not row_locks
    assert selected.count() == len(links)
    assert not AuditLog.objects.filter(action="organization.link_deleted").exists()
