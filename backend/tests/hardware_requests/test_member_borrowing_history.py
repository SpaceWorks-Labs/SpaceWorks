"""Own history is account-scoped and independent of membership and the payment rail."""
import json
from types import SimpleNamespace

import pytest
from django.urls import path, resolve
from django.utils import timezone
from drf_spectacular.generators import SchemaGenerator
from rest_framework.test import APIClient, APIRequestFactory, force_authenticate

from apps.accounts.models import User
from apps.evidence.models import EvidencePhoto
from apps.hardware_requests.models import HardwareRequest, HardwareRequestItem, PublicToolLoan, ReturnEvent
from apps.hardware_requests.member_history_views import MemberBorrowingHistoryView
from apps.makerspaces.models import MakerspaceMembership
from apps.makerspaces.module_registry import core_module_keys
from tests.accounts.ua1_helpers import merged_shell
from tests.return_helpers import authenticated_client, make_product, make_space, make_user

pytestmark = pytest.mark.django_db


@pytest.fixture
def own_history():
    space = make_space("own-borrowing-history")
    space.enabled_modules = sorted(core_module_keys())
    space.enabled_features = ["loans.enabled"]
    space.save(update_fields=["enabled_modules", "enabled_features"])
    owner = make_user("own-borrower")
    other = make_user("other-borrower")
    product = make_product(space, storage_location="PRIVATE-SHELF")
    assert not MakerspaceMembership.objects.filter(user=owner, makerspace=space).exists()
    return SimpleNamespace(space=space, owner=owner, other=other, product=product,
                           client=authenticated_client(owner), url=f"/api/v1/member/makerspaces/{space.pk}/borrowing-history")


def request_row(world, *, owner=None, space=None, status="pending_approval"):
    owner, space = owner or world.owner, space or world.space
    row = HardwareRequest.objects.create(makerspace=space, requester=owner, status=status,
        requester_username="PRIVATE-IDENTITY", requester_name="PRIVATE-NAME", requester_contact_email=world.owner.email,
        requester_contact_phone="PRIVATE-PHONE", issue_remark="PRIVATE-REMARK",
        issued_at=timezone.now() if status in {"issued", "returned", "partially_returned"} else None,
        closed_at=timezone.now() if status in {"returned", "cancelled", "rejected", "expired"} else None)
    product = world.product if space.pk == world.space.pk else make_product(space)
    HardwareRequestItem.objects.create(request=row, product=product, requested_quantity=2,
        accepted_quantity=2, issued_quantity=2 if status == "returned" else 0,
        returned_quantity=2 if status == "returned" else 0)
    return row


def test_account_only_owner_gets_all_own_states_and_no_contact_or_cross_tenant_matches(own_history):
    w = own_history
    wanted = [request_row(w, status=status) for status in ("pending_approval", "accepted", "returned", "cancelled", "expired", "rejected")]
    request_row(w, owner=w.other)  # Same free-text contact, different real owner.
    request_row(w, space=make_space("own-borrowing-foreign-space"))  # Same owner, other tenant.
    response = w.client.get(w.url)
    assert response.status_code == 200
    assert response.data["count"] == len(wanted)
    assert {row["id"] for row in response.data["results"]} == {row.pk for row in wanted}
    assert "membership" not in w.space.enabled_modules and "payments" not in w.space.enabled_modules
    text = json.dumps(response.data)
    for forbidden in ("PRIVATE-IDENTITY", "PRIVATE-NAME", "PRIVATE-PHONE", "PRIVATE-REMARK", "PRIVATE-SHELF", w.owner.email,
                      "evidence", "qr_code", "asset_ids", "public_token", "object_key", "assigned_box"):
        assert forbidden not in text


def test_a_different_account_gets_no_owner_history_even_with_matching_contact(own_history):
    w = own_history
    request_row(w)
    response = authenticated_client(w.other).get(w.url)
    assert response.status_code == 200
    assert response.data == {"count": 0, "next": None, "previous": None, "results": []}


def test_direct_and_self_checkout_backing_requests_are_not_duplicated_and_returns_have_real_dates(own_history):
    w = own_history
    for source in (PublicToolLoan.Source.ADMIN_DIRECT, PublicToolLoan.Source.PUBLIC_SELF_CHECKOUT):
        row = request_row(w, status="returned")
        loan = PublicToolLoan.objects.create(makerspace=w.space, requester=w.owner, request=row,
            source=source, target_type="product", target_id=w.product.pk, target_label=w.product.name,
            status=PublicToolLoan.Status.RETURNED, returned_at=timezone.now())
        evidence = EvidencePhoto.objects.create(makerspace=w.space, evidence_type="return",
            object_key=f"private-history-{row.pk}", uploaded_by=w.owner)
        event = ReturnEvent.objects.create(makerspace=w.space, request=row, evidence=evidence,
            actor=w.owner, remark="PRIVATE-RETURN-REMARK")
    response = w.client.get(w.url)
    assert response.status_code == 200 and response.data["count"] == 2
    assert {item["source"] for item in response.data["results"]} == {"admin_direct", "public_self_checkout"}
    item = next(item for item in response.data["results"] if item["id"] == row.pk)
    assert item["issued_at"] and item["checked_out_at"] == loan.checked_out_at.isoformat()
    assert item["returned_at"] == loan.returned_at.isoformat()
    assert item["returns"][0]["returned_at"] == event.created_at.isoformat().replace("+00:00", "Z")
    assert item["items"][0]["returned_quantity"] == 2
    assert "PRIVATE-RETURN-REMARK" not in json.dumps(response.data)


def test_history_is_paginated_and_period_filters_do_not_truncate_to_dashboard_twenty(own_history):
    w = own_history
    for _ in range(25):
        request_row(w, status="returned")
    active = request_row(w, status="accepted")
    first, second = w.client.get(w.url), w.client.get(w.url, {"page": 2})
    assert first.status_code == second.status_code == 200
    assert first.data["count"] == 26 and len(first.data["results"]) == 24 and len(second.data["results"]) == 2
    assert first.data["next"] and second.data["previous"]
    assert not ({row["id"] for row in first.data["results"]} & {row["id"] for row in second.data["results"]})
    current = w.client.get(w.url, {"period": "current"})
    assert [row["id"] for row in current.data["results"]] == [active.pk]
    assert w.client.get(w.url, {"period": "history"}).data["count"] == 25
    assert w.client.get(w.url, {"period": "foreign"}).status_code == 400
    assert w.client.get(w.url, {"page": 999}).status_code == 404


def test_an_inconsistent_foreign_tenant_return_never_enters_owned_history(own_history):
    w = own_history
    row = request_row(w, status="returned")
    foreign = make_space("history-foreign-return")
    evidence = EvidencePhoto.objects.create(makerspace=foreign, evidence_type="return",
        object_key="foreign-private-history-return", uploaded_by=w.other)
    # A defensive read boundary must not trust a stale/imported secondary tenant FK.
    ReturnEvent.objects.create(makerspace=foreign, request=row, evidence=evidence,
        actor=w.other, remark="FOREIGN-RETURN-REMARK")
    response = w.client.get(w.url)
    assert response.status_code == 200
    assert response.data["results"][0]["id"] == row.pk
    assert response.data["results"][0]["returns"] == []


def test_merged_account_ownership_is_read_without_widening_normal_workflow_scope(own_history):
    w = own_history
    prior = request_row(w, owner=w.other)
    merged_shell(w.other, w.owner)
    response = w.client.get(w.url)
    assert response.status_code == 200
    assert [row["id"] for row in response.data["results"]] == [prior.pk]
    from apps.accounts.rbac_borrowers import scope_by_borrower
    assert not scope_by_borrower(w.owner, HardwareRequest.objects.all(), makerspace=w.space).exists()


@pytest.mark.parametrize("condition", ["restricted", "suspended", "inactive", "walk_in", "revoked"])
def test_account_or_membership_restrictions_refuse_the_owners_own_rows(own_history, condition):
    w = own_history
    request_row(w)
    if condition == "revoked":
        role = w.space.roles.get(slug="member")
        MakerspaceMembership.objects.create(makerspace=w.space, user=w.owner, role="custom", assigned_role=role, status="revoked")
    elif condition == "inactive":
        w.owner.is_active = False
        w.owner.save(update_fields=["is_active"])
    elif condition == "walk_in":
        w.owner.is_walk_in = True
        w.owner.save(update_fields=["is_walk_in"])
    else:
        w.owner.access_status = condition
        w.owner.save(update_fields=["access_status"])
    assert authenticated_client(w.owner).get(w.url).status_code == 403


@pytest.mark.parametrize("state", ["suspended", "archived"])
def test_unservable_space_has_no_owner_history_surface(own_history, state):
    w = own_history
    request_row(w)
    w.space.lifecycle_state = state
    w.space.save(update_fields=["lifecycle_state"])
    assert w.client.get(w.url).status_code == 404


def test_missing_space_and_disabled_lending_are_not_found(own_history):
    w = own_history
    assert w.client.get("/api/v1/member/makerspaces/999999999/borrowing-history").status_code == 404
    request_row(w)
    w.space.enabled_features = []
    w.space.save(update_fields=["enabled_features"])
    response = w.client.get(w.url)
    assert response.status_code == 404 and response.data["feature"] == "loans.enabled"


def test_disabled_workflow_module_is_not_bypassed(own_history, monkeypatch):
    from apps.makerspaces import guards
    w = own_history
    request_row(w)
    original = guards.module_enabled
    monkeypatch.setattr(guards, "module_enabled", lambda space, key: False if key == "request_workflow" else original(space, key))
    response = w.client.get(w.url)
    assert response.status_code == 404 and response.data["module"] == "request_workflow"


def test_unauthenticated_platform_claim_and_api_client_cannot_read_person_history(own_history):
    w = own_history
    request_row(w)
    assert APIClient().get(w.url).status_code == 401
    platform = make_user("history-platform", role=User.Role.SUPERADMIN)
    assert authenticated_client(platform).get(w.url).status_code == 403
    for protocol in ("claim", "api_client"):
        request = APIRequestFactory().get(w.url)
        force_authenticate(request, user=w.owner)
        if protocol == "claim":
            w.owner._claim_audit_context = SimpleNamespace(makerspace_id=w.space.pk)
        else:
            request.api_client = SimpleNamespace(pk=1)
        response = MemberBorrowingHistoryView.as_view()(request, makerspace_id=w.space.pk)
        assert response.status_code == 403
        if protocol == "claim":
            del w.owner._claim_audit_context


def test_history_has_explicit_claim_api_client_and_origin_route_classification(own_history):
    from apps.accounts.claim_routes import CLAIM_ROUTES
    from apps.accounts.claim_route_types import Refused
    from apps.apiclients.scope_registry import lookup
    from apps.makerspaces.origin_scope_routes import authoritative_route_resolution
    w = own_history
    match = resolve(w.url)
    assert match.view_name == "hardware_requests:member-borrowing-history"
    for method in ("GET", "HEAD"):
        assert isinstance(CLAIM_ROUTES[match.view_name, method], Refused)
        assert lookup(match.view_name, method) is None
    request = APIRequestFactory().get(w.url)
    request.resolver_match = match
    assert authoritative_route_resolution(request) == ({w.space.pk}, True)
    assert w.client.head(w.url).status_code == 200


def test_openapi_documents_auth_period_pagination_and_allowlisted_history():
    patterns = [path("api/v1/member/makerspaces/<int:makerspace_id>/borrowing-history", MemberBorrowingHistoryView.as_view())]
    schema = SchemaGenerator(patterns=patterns).get_schema(request=None, public=True)
    operation = next(iter(schema["paths"].values()))["get"]
    assert operation["security"]
    assert {item["name"] for item in operation["parameters"]} >= {"page", "period", "makerspace_id"}
    assert {"200", "400", "401", "403", "404"} <= operation["responses"].keys()
    history = schema["components"]["schemas"]["OwnBorrowingHistory"]["properties"]
    assert {"items", "returns", "status", "issued_at", "returned_at", "closed_at"} <= history.keys()
    assert not {"requester", "evidence", "qr_code", "asset_ids", "object_key", "requester_contact_email"} & history.keys()


def test_rows_carry_can_renew_and_refusal_for_an_account_only_borrower(own_history):
    """221a: membership off, member_accounts on, `account_self_renewal` admits the self-renewal."""
    from apps.makerspaces.models_loan_policy import MakerspaceLoanPolicy
    w = own_history
    w.space.enabled_modules = sorted(set(w.space.enabled_modules) | {"member_accounts"} - {"membership"})
    w.space.enabled_features = ["loans.enabled", "loans.renewals"]
    w.space.save(update_fields=["enabled_modules", "enabled_features"])
    policy = MakerspaceLoanPolicy.for_makerspace(w.space)
    policy.loan_renewal_mode = MakerspaceLoanPolicy.RenewalMode.AUTO
    policy.account_self_renewal = False
    policy.save()
    row = request_row(w, status="issued")
    row.return_due_at = timezone.now() + timezone.timedelta(days=2)
    row.save(update_fields=["return_due_at"])
    closed = request_row(w, status="returned")

    by_id = {item["id"]: item for item in w.client.get(w.url).data["results"]}
    assert by_id[row.pk]["can_renew"] is False and by_id[row.pk]["renewal_refusal"] == "self_renewal_off"
    assert by_id[closed.pk]["can_renew"] is False and by_id[closed.pk]["renewal_refusal"] == "loan_not_active"

    policy.account_self_renewal = True
    policy.save()
    by_id = {item["id"]: item for item in w.client.get(w.url).data["results"]}
    assert by_id[row.pk]["can_renew"] is True and by_id[row.pk]["renewal_refusal"] is None


def test_renewals_switch_off_refuses_every_active_row(own_history):
    w = own_history
    row = request_row(w, status="issued")
    row.return_due_at = timezone.now() + timezone.timedelta(days=2)
    row.save(update_fields=["return_due_at"])
    item = next(i for i in w.client.get(w.url).data["results"] if i["id"] == row.pk)
    assert item["can_renew"] is False and item["renewal_refusal"] == "renewals_off"
