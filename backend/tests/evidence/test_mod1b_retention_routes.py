"""MOD-1B: the evidence retention HTTP routes (policy GET/PATCH, preview POST), condition by condition.

Complements test_object_retention.py (happy path + one role refusal) with the boundaries, tenancy, module switch,
audit and idempotency conditions of the checklist. Every refusal asserts the exact status and, where the body
carries one, the exact code.
"""

import pytest
from django.urls import reverse

from apps.audit.models import AuditLog
from apps.evidence.models import EvidenceRetentionPolicy
from tests.evidence.test_object_retention import client_for, make_manager, make_space, policy_url, preview_url
from tests.account_split.p1_helpers import staff

pytestmark = pytest.mark.django_db


@pytest.fixture
def setup():
    space = make_space("mod1b-ret")
    return space, make_manager("mod1b-ret-manager", space)


@pytest.mark.parametrize("days", [30, 3650])
def test_retention_days_accept_both_boundaries_and_audit_once_each(setup, days):
    space, manager = setup
    reply = client_for(manager).patch(policy_url(space), {"object_retention_days": days}, format="json")
    assert reply.status_code == 200 and reply.data["override_days"] == days and reply.data["effective_days"] == days
    assert EvidenceRetentionPolicy.objects.get(makerspace=space).object_retention_days == days
    entry = AuditLog.objects.get(action="evidence.retention_policy_updated", makerspace=space)
    assert (entry.meta["new_effective_days"], entry.meta["override_cleared"]) == (days, False)


@pytest.mark.parametrize("body, field", [
    ({"object_retention_days": 29}, "object_retention_days"),
    ({"object_retention_days": 3651}, "object_retention_days"),
    ({"object_retention_days": 0}, "object_retention_days"),
    ({"object_retention_days": -5}, "object_retention_days"),
    ({"object_retention_days": "abc"}, "object_retention_days"),
    ({"object_retention_days": 1.5}, "object_retention_days"),
    ({"abandoned_upload_retention_days": 0}, "abandoned_upload_retention_days"),
    ({"abandoned_upload_retention_days": 3651}, "abandoned_upload_retention_days"),
    ({"abandoned_upload_cleanup_enabled": "maybe"}, "abandoned_upload_cleanup_enabled"),
    ({}, "non_field_errors"),
])
def test_invalid_policy_bodies_are_refused_with_the_field_and_write_nothing(setup, body, field):
    space, manager = setup
    reply = client_for(manager).patch(policy_url(space), body, format="json")
    assert reply.status_code == 400 and field in reply.data, reply.data
    assert not EvidenceRetentionPolicy.objects.exists()
    assert not AuditLog.objects.filter(action="evidence.retention_policy_updated").exists()


def test_the_abandoned_upload_age_must_outlast_the_presign_lifetime(setup, settings):
    space, manager = setup
    settings.EVIDENCE_URL_TTL_SECONDS = 2 * 86400
    refused = client_for(manager).patch(policy_url(space), {"abandoned_upload_retention_days": 2}, format="json")
    assert refused.status_code == 400 and "abandoned_upload_retention_days" in refused.data
    allowed = client_for(manager).patch(policy_url(space), {"abandoned_upload_retention_days": 3}, format="json")
    assert allowed.status_code == 200 and allowed.data["abandoned_upload_override_days"] == 3
    assert allowed.data["abandoned_upload_effective_days"] == 3


def test_a_repeated_identical_patch_keeps_one_row_and_a_default_patch_removes_it(setup):
    space, manager = setup
    for _ in range(2):
        assert client_for(manager).patch(policy_url(space), {"object_retention_days": 90}, format="json").status_code == 200
    assert EvidenceRetentionPolicy.objects.filter(makerspace=space).count() == 1
    back = client_for(manager).patch(policy_url(space), {"object_retention_days": None}, format="json")
    assert back.status_code == 200 and back.data["override_days"] is None
    assert not EvidenceRetentionPolicy.objects.filter(makerspace=space).exists()


@pytest.mark.parametrize("limit", [0, -1, 1001, "x"])
def test_preview_limit_outside_1_to_1000_is_refused(setup, limit):
    space, manager = setup
    reply = client_for(manager).post(preview_url(space), {"limit": limit}, format="json")
    assert reply.status_code == 400 and "limit" in reply.data


@pytest.mark.parametrize("limit", [1, 1000])
def test_preview_limit_boundaries_are_accepted_and_the_preview_writes_nothing(setup, limit):
    space, manager = setup
    reply = client_for(manager).post(preview_url(space), {"limit": limit}, format="json")
    assert reply.status_code == 200 and reply.data["object_candidates"] == 0 and reply.data["has_more"] is False
    assert not AuditLog.objects.filter(action="evidence.retention_policy_updated").exists()


def test_another_makerspaces_manager_gets_404_on_every_retention_route(setup):
    space, _manager = setup
    other = make_space("mod1b-ret-other")
    outsider = make_manager("mod1b-ret-outsider", other)
    client = client_for(outsider)
    assert client.get(policy_url(space)).status_code == 404
    assert client.patch(policy_url(space), {"object_retention_days": 90}, format="json").status_code == 404
    assert client.post(preview_url(space), {"limit": 5}, format="json").status_code == 404
    assert client.get(reverse("evidence_admin:evidence-retention-policy", kwargs={"makerspace_id": 999999})).status_code == 404
    assert not EvidenceRetentionPolicy.objects.exists()


def test_roles_below_manage_makerspace_are_refused_with_403_and_nothing_changes(setup):
    space, _manager = setup
    for role in ("inventory_manager", "machine_manager"):
        user, _ = staff(space, f"mod1b-ret-{role}", role=role)
        client = client_for(user)
        assert client.get(policy_url(space)).status_code == 403, role
        assert client.patch(policy_url(space), {"object_retention_days": 90}, format="json").status_code == 403, role
        assert client.post(preview_url(space), {}, format="json").status_code == 403, role
    assert not EvidenceRetentionPolicy.objects.exists()


def test_signed_out_callers_are_refused(setup):
    from rest_framework.test import APIClient

    space, _ = setup
    anonymous = APIClient()
    assert anonymous.get(policy_url(space)).status_code == 401
    assert anonymous.patch(policy_url(space), {"object_retention_days": 90}, format="json").status_code == 401
    assert not EvidenceRetentionPolicy.objects.exists()


def test_evidence_uploads_is_a_core_module_so_the_retention_routes_have_no_off_switch(setup):
    from apps.makerspaces.module_install import ModuleInstallError, uninstall_module

    space, manager = setup
    with pytest.raises(ModuleInstallError, match="core module"):
        uninstall_module(space, "evidence_uploads")
    assert client_for(manager).get(policy_url(space)).status_code == 200
