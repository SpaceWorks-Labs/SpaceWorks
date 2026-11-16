"""Resource pages share feature checks per tenant, never across responses."""

from apps.accounts.models import User
from tests.account_split_g2_helpers import grant_organization_action

from collections import Counter
from unittest.mock import patch

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from apps.bookings.models import BookableSpace
from apps.bookings.serializers_admin import BookableSpaceAdminSerializer
from apps.makerspaces.models import MakerspaceMembership
from apps.makerspaces.capability_eligibility import configuration_feature_enabled
from tests.bookings.staff_grant_helpers import client_for, grant_fixture

pytestmark = pytest.mark.django_db
LIST_ROUTES = ["admin-accessible-booking-spaces", "admin-bookable-space-list-create"]


def list_url(route, tenant):
    return reverse(route, args=[tenant.pk] if route == "admin-bookable-space-list-create" else [])


@pytest.mark.parametrize("route", LIST_ROUTES)
@pytest.mark.parametrize("page_size", [24, 200])
def test_resource_page_query_count_does_not_grow_with_resources(route, page_size, django_assert_num_queries):
    tenant, manager, _, resource, _, _ = grant_fixture()
    BookableSpace.objects.bulk_create([
        BookableSpace(makerspace=tenant, name=f"Room {index:03}") for index in range(page_size - 1)
    ])
    client = client_for(manager)
    url = list_url(route, tenant)
    with CaptureQueriesContext(connection) as queries:
        first = client.get(url, {"page_size": 1})
        assert first.status_code == 200, first.data
        assert len(first.data["results"]) == 1
    with django_assert_num_queries(len(queries)):
        response = client.get(url, {"page_size": page_size})
        assert response.status_code == 200, response.data
        assert len(response.data["results"]) == page_size
    assert resource.pk in {row["id"] for row in response.data["results"]}
    assert all(row["recurring_enabled"] and row["staff_grants_enabled"]
               for row in response.data["results"])


def test_mixed_tenant_page_evaluates_each_feature_once_per_tenant():
    tenant, manager, _, _, _, _ = grant_fixture()
    other, other_manager, _, _, _, _ = grant_fixture(slug="other-page-features")
    manager = User.objects.create_user(username="mixed-page-organization-manager")
    grant_organization_action(tenant, manager, "manage_bookings")
    grant_organization_action(other, manager, "manage_bookings")
    tenant.enabled_features.remove("bookings.recurring")
    tenant.save(update_fields=["enabled_features"])
    other.enabled_features.remove("bookings.staff_grants")
    other.save(update_fields=["enabled_features"])
    for makerspace in (tenant, other):
        BookableSpace.objects.create(makerspace=makerspace, name="Another room")
    with patch("apps.bookings.booking_authority_page.configuration_feature_enabled", wraps=configuration_feature_enabled) as check:
        response = client_for(manager).get(reverse("admin-accessible-booking-spaces"))
    assert response.status_code == 200, response.data
    assert len(response.data["results"]) == 4
    assert Counter((call.args[0].pk, call.args[1]) for call in check.call_args_list) == Counter({
        (pk, key): 1 for pk in (tenant.pk, other.pk)
        for key in ("bookings.recurring", "bookings.staff_grants", "bookings.clone", "bookings.staff_tools", "bookings.broadcasts", "bookings.passes", "bookings.checkin",
                    "bookings.website", "bookings.embed")
    })
    for row in response.data["results"]:
        assert row["recurring_enabled"] is (row["makerspace_id"] == other.pk)
        assert row["staff_grants_enabled"] is (row["makerspace_id"] == tenant.pk)


@pytest.mark.parametrize("route", LIST_ROUTES)
def test_resource_page_feature_context_is_fresh_on_next_request(route):
    tenant, manager, *_ = grant_fixture()
    client = client_for(manager)
    url = list_url(route, tenant)
    initial = client.get(url)
    assert initial.status_code == 200, initial.data
    assert initial.data["results"][0]["recurring_enabled"] is True
    assert initial.data["results"][0]["staff_grants_enabled"] is True
    tenant.enabled_features = [key for key in tenant.enabled_features if not key.startswith("bookings.")]
    tenant.save(update_fields=["enabled_features"])
    updated = client.get(url)
    assert updated.status_code == 200, updated.data
    assert updated.data["results"][0]["recurring_enabled"] is False
    assert updated.data["results"][0]["staff_grants_enabled"] is False


def test_serializer_without_page_context_shares_tenant_feature_checks(django_assert_max_num_queries):
    tenant, _, _, resource, _, _ = grant_fixture()
    sibling = BookableSpace.objects.create(makerspace=tenant, name="Sibling room")
    rows = list(BookableSpace.objects.filter(pk__in=[resource.pk, sibling.pk]).select_related("makerspace"))
    context = {"booking_authority": {row.pk: (False, []) for row in rows}}
    # Shared per tenant: at most one query (capability checks may now read the loaded row).
    with django_assert_max_num_queries(1):
        data = BookableSpaceAdminSerializer(rows, many=True, context=context).data
    assert all(row["recurring_enabled"] and row["staff_grants_enabled"] for row in data)


@pytest.mark.parametrize("state, expected", [
    ("module_off", False), ("importing", False), ("archived", True),
])
def test_single_resource_features_preserve_recovery_and_capability_gates(state, expected):
    tenant, _, _, resource, _, _ = grant_fixture()
    if state == "module_off":
        tenant.enabled_modules.remove("bookings")
        tenant.save(update_fields=["enabled_modules"])
    elif state == "importing":
        tenant.lifecycle_state = "importing"
        tenant.save(update_fields=["lifecycle_state"])
    else:
        tenant.archived_at = timezone.now()
        tenant.save(update_fields=["archived_at"])
    # The detail serializer must still work without the list view's prebuilt context.
    resource = BookableSpace.objects.select_related("makerspace").get(pk=resource.pk)
    data = BookableSpaceAdminSerializer(resource).data
    assert data["recurring_enabled"] is expected
    assert data["staff_grants_enabled"] is expected
