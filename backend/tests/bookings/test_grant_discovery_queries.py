"""Resource authority stays live without adding authentication queries per tenant."""

from dataclasses import replace

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.accounts import mfa_policy
from apps.accounts.serializers_payload import user_payload
from apps.bookings.booking_authority import active_grants
from apps.bookings.staff_payload import granted_booking_entries, has_grant_authority
from apps.makerspaces.capabilities import FEATURES
from apps.makerspaces.capability_eligibility import feature_enabled_servable_ids
from apps.makerspaces.platform import feature_enabled
from tests.bookings.staff_grant_helpers import grant_fixture

pytestmark = pytest.mark.django_db
FEATURE = "bookings.staff_grants"


def discover(user, consumer):
    if consumer == "grants":
        return {row.space_id for row in active_grants(user)}
    if consumer == "entries":
        return {row["space_id"] for row in granted_booking_entries(user)}
    if consumer == "payload":
        return {row["space_id"] for row in user_payload(user)["booking_grants"]}
    if consumer == "authority":
        return has_grant_authority(user)
    return mfa_policy.required(user)


@pytest.mark.parametrize("consumer", ["grants", "entries", "payload", "authority", "mfa"])
def test_discovery_query_count_is_constant_across_tenants(consumer, django_assert_num_queries):
    tenant, _, user, resource, _, _ = grant_fixture(slug="query-one")
    tenant.enabled_features.append("security.staff_mfa_required")
    # Security keys change only through the security service; write the fixture row directly.
    type(tenant).objects.filter(pk=tenant.pk).update(enabled_features=tenant.enabled_features)
    expected = {resource.pk}
    discover(user, consumer)  # S-A: the first payload opens the person's staff-MFA grace (one write)
    with CaptureQueriesContext(connection) as queries:
        assert discover(user, consumer) == (True if consumer in {"authority", "mfa"} else expected)
    for index in range(5):
        tenant, _, _, resource, grant, _ = grant_fixture(slug=f"query-many-{index}")
        tenant.enabled_features.append("security.staff_mfa_required")
        # Security keys change only through the security service; write the fixture row directly.
        type(tenant).objects.filter(pk=tenant.pk).update(enabled_features=tenant.enabled_features)
        grant.user = user
        grant.save(update_fields=["user"])
        expected.add(resource.pk)
    with django_assert_num_queries(len(queries)):
        assert discover(user, consumer) == (True if consumer in {"authority", "mfa"} else expected)


@pytest.mark.parametrize("state", [
    "feature_off", "module_off", "archived", "importing",
    "revoked", "invalid_permissions", "suspended",
])
def test_batched_discovery_rechecks_live_authority(state):
    tenant, _, user, resource, grant, _ = grant_fixture()
    assert {row.space_id for row in active_grants(user)} == {resource.pk}
    if state == "feature_off":
        tenant.enabled_features.remove(FEATURE)
        tenant.save(update_fields=["enabled_features"])
    elif state == "module_off":
        tenant.enabled_modules.remove("bookings")
        tenant.save(update_fields=["enabled_modules"])
    elif state == "archived":
        tenant.archived_at = timezone.now()
        tenant.save(update_fields=["archived_at"])
    elif state == "importing":
        tenant.lifecycle_state = "importing"
        tenant.save(update_fields=["lifecycle_state"])
    elif state == "revoked":
        grant.revoked_at = timezone.now()
        grant.save(update_fields=["revoked_at"])
    elif state == "invalid_permissions":
        grant.permissions = ["unknown_permission"]
        grant.save(update_fields=["permissions"])
    else:
        # The already-loaded actor must not hide a live suspension.
        type(user).objects.filter(pk=user.pk).update(access_status="suspended")
    assert not active_grants(user).exists()
    assert not has_grant_authority(user)
    assert user_payload(user)["booking_grants"] == []


@pytest.mark.parametrize("state, expected", [
    ("enabled", True), ("explicit_off", False), ("default_off", False), ("unknown", False),
    ("missing_module", False), ("tombstoned", False),
    ("missing_feature", False), ("nested_enabled", True),
    ("nested_tombstone", False), ("invalid_parent", False),
])
def test_batch_and_single_tenant_use_same_feature_prerequisites(monkeypatch, state, expected):
    tenant, _, user, _, _, _ = grant_fixture()
    definition = FEATURES[FEATURE]
    key = FEATURE
    if state in {"explicit_off", "default_off"}:
        tenant.enabled_features.remove(FEATURE)
        if state == "default_off":
            monkeypatch.setitem(FEATURES, FEATURE, replace(definition, default_enabled=True))
    elif state == "unknown":
        key = "bookings.unknown"
        tenant.enabled_features.append(key)
    elif state == "missing_module":
        monkeypatch.setitem(FEATURES, FEATURE, replace(definition, requires_modules=("events",)))
        tenant.enabled_modules = [module for module in tenant.enabled_modules if module != "events"]
    elif state == "missing_feature":
        monkeypatch.setitem(FEATURES, FEATURE, replace(definition, requires_features=("bookings.recurring",)))
        tenant.enabled_features.remove("bookings.recurring")
    elif state == "invalid_parent":
        monkeypatch.setitem(FEATURES, FEATURE, replace(definition, parent_module="unknown"))
    elif state in {"tombstoned", "nested_enabled", "nested_tombstone"}:
        tombstone = "bookings" if state == "tombstoned" else "events"
        if state != "tombstoned":
            monkeypatch.setitem(FEATURES, FEATURE, replace(definition, requires_features=("events.organization_audience",)))
            tenant.enabled_modules.append("events")
            tenant.enabled_features.append("events.organization_audience")
        if state != "nested_enabled":
            from apps.separability import registry
            runtime_active = registry.runtime_active
            monkeypatch.setattr(registry, "runtime_active", lambda label: label != tombstone and runtime_active(label))
    tenant.save(update_fields=["enabled_modules", "enabled_features"])
    assert feature_enabled(tenant, key) is expected
    assert (tenant.pk in feature_enabled_servable_ids([tenant.pk], key)) is expected
    if key == FEATURE:
        assert has_grant_authority(user) is expected


def test_shared_policy_keeps_loan_master_and_archived_capability_semantics():
    tenant, *_ = grant_fixture()
    tenant.enabled_features = ["inventory.self_checkout"]
    tenant.save(update_fields=["enabled_features"])
    assert not feature_enabled(tenant, "inventory.self_checkout")
    assert not feature_enabled_servable_ids([tenant.pk], "inventory.self_checkout")
    tenant.enabled_features.append("loans.enabled")
    tenant.save(update_fields=["enabled_features"])
    assert feature_enabled(tenant, "inventory.self_checkout")
    assert feature_enabled_servable_ids([tenant.pk], "inventory.self_checkout") == {tenant.pk}
    tenant.archived_at = timezone.now()
    tenant.save(update_fields=["archived_at"])
    # Capability queries retain archived semantics; live discovery excludes them.
    assert feature_enabled(tenant, "inventory.self_checkout")
    assert not feature_enabled_servable_ids([tenant.pk], "inventory.self_checkout")
