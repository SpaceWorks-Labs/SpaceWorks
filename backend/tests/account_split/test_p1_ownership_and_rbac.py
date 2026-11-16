from types import SimpleNamespace

import pytest
from django.db import transaction
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.accounts import rbac
from apps.accounts.models import User
from apps.accounts.rbac_roles import additional_role_exists, direct_role_filter, membership_roles, role_slug_filter
from apps.makerspaces.models import Makerspace, MakerspaceMembership
from .p1_helpers import raw_membership, sql, staff

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture(params=[
    # Decision 63 reverses the member/staff account split: a person holding a staff role IS a
    # member-kind account, so "a staff account is not a member" no longer holds. Platform stays.
    pytest.param("staff", marks=pytest.mark.skip(reason="decision 63: one account per person; staff roles live on a person")),
    "platform",
])
def nonmember(request):
    if request.param == "platform": return User.objects.create_superuser("operator")
    space = Makerspace.objects.create(name="Staff", slug="staff")
    return staff(space)[0]


def _event():
    from datetime import timedelta
    from django.utils import timezone
    from apps.events.models import Event
    space = Makerspace.objects.create(name="Community events", slug="p1-boundary-events")
    start = timezone.now() + timedelta(days=1)
    return Event.objects.create(makerspace=space, title="Boundary", status=Event.Status.PUBLISHED,
                                starts_at=start, ends_at=start + timedelta(hours=2), is_public=True)


def ownership_calls(user):
    from apps.bookings.services_bookings import create_booking
    from apps.events.services_registration import register
    from apps.hardware_requests.direct_loan_workflow import issue_direct_loan
    from apps.hardware_requests.request_workflow import submit_request
    from apps.hardware_requests.self_checkout_issue import checkout_tool
    from apps.machines.service_workflow_actions import submit
    from apps.makerspaces.member_card_services import issue_card, reissue_card
    from apps.makerspaces.membership_activation import _activate_membership
    from apps.makerspaces.membership_admission import claim_invitation, request_membership
    from apps.makerspaces.membership_legacy import legacy_claim_invitation, legacy_request_membership
    from apps.makerspaces.membership_plan_services import create_term
    from apps.makerspaces.profile_services import profile_for, save_profile
    from apps.makerspaces.public_profile_handles import claim_handle
    from apps.makerspaces.self_service_access import own_membership
    from apps.makerspaces.waiver_services import accept_waiver
    from apps.payments.services import create_payment
    from apps.presence.services import staff_check_in, start_session

    membership = SimpleNamespace(user=user)
    return [
        lambda: own_membership(user, None),
        lambda: profile_for(membership), lambda: save_profile(membership, {}),
        lambda: claim_handle(membership.user, "handle"), lambda: issue_card(user, membership),
        lambda: reissue_card(user, SimpleNamespace(membership=membership), reason="lost"),
        lambda: create_term(user, membership, None), lambda: accept_waiver(membership),
        lambda: start_session(user, None, 60), lambda: staff_check_in(user, user, None, 60),
        lambda: create_booking(None, starts_at=None, ends_at=None, member=user),
        # The registration write boundary resolves its event before the service body
        # runs, so this boundary needs a real event to reach the member check.
        lambda: register(_event(), member=user),
        lambda: create_payment(makerspace=None, subject_type="booking", subject_id=1, member=user,
                               amount=1, currency="usd", created_by=user),
        lambda: submit_request(None, [], "test", requester_principal=user, contact_snapshot=None, audit_actor=user),
        lambda: issue_direct_loan(None, user, borrower=user, evidence_id=1, remark="", qr_payloads=[], items=[]),
        lambda: checkout_tool(None, user, "qr", evidence_id=1),
        lambda: submit(None, user, requester_name="", contact_email="", contact_phone="", title="test"),
        lambda: _activate_membership(user, None, user, None, source="test"),
        lambda: request_membership(user, None), lambda: claim_invitation(user, 1),
        lambda: legacy_request_membership(user, None), lambda: legacy_claim_invitation(user, 1),
    ]


def test_all_community_service_boundaries_refuse_nonmembers(nonmember):
    for call in ownership_calls(nonmember):
        with pytest.raises(PermissionDenied) as caught: call()
        assert caught.value.get_codes() == "member_account_required"


def test_membership_invitations_refuse_staff_role_sets():
    from apps.makerspaces.membership_legacy import invite_membership
    space = Makerspace.objects.create(name="Community", slug="community")
    root = User.objects.create_superuser("root")
    with pytest.raises(ValidationError):
        invite_membership(root, space, "new@example.test", space.roles.get(slug="handover"))


@pytest.mark.parametrize("corruption", ["member_staff_role", "platform_membership", "null_primary",
                                         "foreign_primary", "foreign_tenant", "invalid_status",
                                         "second_membership", "member_additional", "sm_additional"])
def test_object_and_sql_readers_refuse_uncommitted_corruption(corruption):
    a, b = [Makerspace.objects.create(name=slug, slug=slug) for slug in ("rbac-a", "rbac-b")]
    user, membership = staff(a, role="handover")
    root = User.objects.create_superuser("root")
    member = User.objects.create_user("member")
    with transaction.atomic():
        if corruption in {"member_staff_role", "platform_membership"}:
            target = member if corruption == "member_staff_role" else root
            # Decision 63: a person may hold a staff-track row, so the invalid member shape is a
            # COMMUNITY row carrying a staff role; a platform account holds no rows at all.
            raw_membership(membership, user_id=target.pk, **({"track": "community"} if target is member else {}))
            membership = MakerspaceMembership.all_tracks.get(user=target)
        elif corruption == "null_primary":
            sql("UPDATE makerspaces_makerspacemembership SET assigned_role_id=NULL,role='space_manager' WHERE id=%s", [membership.pk])
        elif corruption == "foreign_primary":
            sql("UPDATE makerspaces_makerspacemembership SET assigned_role_id=%s WHERE id=%s", [b.roles.get(slug="handover").pk, membership.pk])
        elif corruption == "foreign_tenant":
            # Decision 63: a staff row in another space is valid, so moving the row AND its role
            # together is no corruption; the foreign shape is a row whose role stays in the old tenant.
            sql("UPDATE makerspaces_makerspacemembership SET makerspace_id=%s WHERE id=%s", [b.pk, membership.pk])
        elif corruption == "invalid_status":
            sql("UPDATE makerspaces_makerspacemembership SET status='invalid' WHERE id=%s", [membership.pk])
        elif corruption == "second_membership":
            # Decision 63: a second staff row in another space is valid for a person; the invalid
            # second row is one holding the Member role on the staff track.
            raw_membership(membership, makerspace_id=b.pk, assigned_role_id=b.roles.get(slug="member").pk)
            membership = MakerspaceMembership.all_tracks.get(user=user, makerspace=b)
        else:
            role = a.roles.get(slug="member" if corruption == "member_additional" else "space_manager")
            sql("INSERT INTO makerspaces_membershipadditionalrole (membership_id,role_id,assigned_at) VALUES (%s,%s,CURRENT_TIMESTAMP)",
                [membership.pk, role.pk])
        membership = MakerspaceMembership.all_tracks.select_related("user", "assigned_role").get(pk=membership.pk)
        assert membership_roles(membership) == []
        assert rbac.actions_for_membership(membership) == set()
        queryset = MakerspaceMembership.all_tracks.filter(pk=membership.pk)
        assert not queryset.filter(direct_role_filter([rbac.Action.VIEW_INVENTORY])).exists()
        assert not queryset.filter(role_slug_filter("handover")).exists()
        assert not queryset.annotate(grants=additional_role_exists(actions=[rbac.Action.MANAGE_MAKERSPACE])).filter(grants=True).exists()
        transaction.set_rollback(True)


def test_valid_combined_roles_and_member_delegation_survive():
    from apps.makerspaces.role_membership_writes import replace_membership_roles
    a = Makerspace.objects.create(name="Valid", slug="valid")
    user, membership = staff(a, role="inventory_manager")
    with transaction.atomic():
        replace_membership_roles(membership=membership,
            roles=[a.roles.get(slug="inventory_manager"), a.roles.get(slug="handover")], actor=user, reason="test")
    membership.refresh_from_db()
    assert rbac.Action.VIEW_INVENTORY in rbac.actions_for_membership(membership)
    assert MakerspaceMembership.staff_tracks.filter(pk=membership.pk).filter(direct_role_filter([rbac.Action.VIEW_INVENTORY])).exists()
    member = User.objects.create_user("member")
    membership = MakerspaceMembership.objects.create(user=member, makerspace=a, role="custom", assigned_role=a.roles.get(slug="member"))
    assert [role.slug for role in membership_roles(membership)] == ["member"]
    assert rbac.actions_for_membership(membership) == set()
