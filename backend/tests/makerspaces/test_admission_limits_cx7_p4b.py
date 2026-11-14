"""Member admission and staff grants contend for their own tenant capacity."""
from types import SimpleNamespace

import pytest
from django.db import connection
from rest_framework.exceptions import APIException

from apps.accounts import staff_account_services
from apps.accounts.staff_invitation_acceptance import accept
from apps.accounts.services_staff_invitations import issue
from apps.accounts.models import EmailVerificationChallenge, StaffInvitation
from apps.audit.models import AuditLog
from apps.makerspaces import membership_services
from apps.makerspaces.membership_activation import _activate_membership
from apps.makerspaces.models import MakerspaceMembership, MembershipRequest, MembershipTerm
from apps.makerspaces.limits_usage import _COUNTERS
from apps.makerspaces.staff_role_grants import grant_staff_role
from apps.payments.models import Payment
from tests.accounts.account_factories import make_membership
from tests.limits_0120.creator_races_cx7 import race_creators
from tests.makerspaces.test_membership_admission_matrix import _setup
from tests.makerspaces.test_membership_j1 import member_role, user

pytestmark = [pytest.mark.django_db, pytest.mark.area_membership, pytest.mark.area_staff_admin]
MEMBER_KINDS = ["open", "approval", "claim", "reactivate"]
STAFF_KINDS = ["grant", "seed_grant", "invite_accept"]


def snapshot():
    return [list(model.objects.order_by("pk").values()) for model in (
        MakerspaceMembership, MembershipRequest, MembershipTerm, StaffInvitation,
        EmailVerificationChallenge, Payment, AuditLog)]


def member_world(kind):
    space, actor, first, _, _ = _setup("approval" if kind == "approval" else "open")
    people = [first, user("cx7-p4b-next-applicant")]
    rows = []
    if kind == "approval":
        for person in people:
            membership_services.request_membership(person, space)
            rows.append(MembershipRequest.objects.get(makerspace=space, user=person))
    elif kind == "claim":
        rows = [membership_services.invite_membership(actor, space, person.email, member_role(space))
                for person in people]
    elif kind == "reactivate":
        for person in people:
            make_membership(person, space, status="revoked")
    baseline = _COUNTERS["members"](space)
    space.resource_limit_overrides = {"members": baseline + 1, "payments_monthly_count": 0}
    space.save(update_fields=["resource_limit_overrides"])
    return space, actor, people, rows, baseline


def admit(w, kind, index):
    space, actor, people, rows, _ = w
    if kind == "approval":
        return membership_services.approve_request(actor, rows[index], member_role(space))
    if kind == "claim":
        return membership_services.claim_invitation(people[index], rows[index].pk)
    if kind == "reactivate":
        return _activate_membership(actor, space, people[index], member_role(space), source="direct")
    return membership_services.request_membership(people[index], space)


@pytest.mark.parametrize("kind", MEMBER_KINDS)
def test_member_admission_max_next_exact_refusal_has_no_rows_or_payment(kind, settings):
    settings.MANAGED_PLANS_ENABLED = False
    w = member_world(kind)
    admit(w, kind, 0)
    assert _COUNTERS["members"](w[0]) == w[4] + 1
    before = snapshot()
    with pytest.raises(APIException) as failure:
        admit(w, kind, 1)
    assert (failure.value.status_code, str(failure.value.detail["code"])) == (400, "limit_reached")
    assert snapshot() == before
    assert Payment.objects.filter(makerspace=w[0]).count() == 0


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("kind", MEMBER_KINDS)
def test_member_admission_race_at_last_slot_has_one_winner(kind, settings):
    if connection.vendor != "postgresql":
        pytest.skip("Requires PostgreSQL row locks")
    settings.MANAGED_PLANS_ENABLED = False
    w = member_world(kind)
    assert race_creators(lambda index: admit(w, kind, index)) == [(201, "created"), (400, "limit_reached")]
    assert _COUNTERS["members"](w[0]) == w[4] + 1
    assert Payment.objects.filter(makerspace=w[0]).count() == 0


def staff_world(kind, monkeypatch):
    space, actor, first, _, _ = _setup("open")
    people = [first, user("cx7-p4b-next-staff")]
    for person in people:
        make_membership(person, space)
    invitations = []
    if kind == "invite_accept":
        monkeypatch.setattr("apps.accounts.login_codes.new_code", lambda: "123456")
        monkeypatch.setattr("apps.accounts.staff_invitation_acceptance._send_code", lambda *args: None)
        for person in people:
            row, token = issue(actor, space.pk, email=person.email, roles=["inventory_manager"])
            assert accept(SimpleNamespace(user=person), token=token, makerspace_slug=space.slug)["challenge_required"] is True
            invitations.append(token)
    baseline = _COUNTERS["staff"](space)
    space.resource_limit_overrides = {"staff": baseline + 1}
    space.save(update_fields=["resource_limit_overrides"])
    return space, actor, people, invitations, baseline


def staff_admit(w, kind, index):
    space, actor, people, invitations, _ = w
    if kind == "invite_accept":
        return accept(SimpleNamespace(user=people[index]), token=invitations[index], makerspace_slug=space.slug, code="123456")
    if kind == "seed_grant":
        return grant_staff_role(makerspace=space, user=people[index], actor=actor,
                                roles=[space.roles.get(slug="inventory_manager")])
    return staff_account_services.grant(actor, space.pk, user_id=people[index].pk, roles=["inventory_manager"])


@pytest.mark.parametrize("kind", STAFF_KINDS)
def test_staff_admission_max_next_exact_refusal_preserves_invitation_and_proof(kind, settings, monkeypatch):
    settings.MANAGED_PLANS_ENABLED = False
    w = staff_world(kind, monkeypatch)
    staff_admit(w, kind, 0)
    assert _COUNTERS["staff"](w[0]) == w[4] + 1
    before = snapshot()
    with pytest.raises(APIException) as failure:
        staff_admit(w, kind, 1)
    assert (failure.value.status_code, str(failure.value.detail["code"])) == (
        (400, "limit_reached") if kind == "seed_grant" else (409, "quota_exceeded"))
    assert snapshot() == before


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("kind", STAFF_KINDS)
def test_staff_admission_race_at_last_slot_has_one_winner(kind, settings, monkeypatch):
    if connection.vendor != "postgresql":
        pytest.skip("Requires PostgreSQL row locks")
    settings.MANAGED_PLANS_ENABLED = False
    w = staff_world(kind, monkeypatch)
    refused = (400, "limit_reached") if kind == "seed_grant" else (409, "quota_exceeded")
    assert race_creators(lambda index: staff_admit(w, kind, index)) == [(201, "created"), refused]
    assert _COUNTERS["staff"](w[0]) == w[4] + 1
    assert AuditLog.objects.filter(makerspace=w[0], action="staff_role.granted").count() == 1


@pytest.mark.parametrize("kind", ["open", "approval", "claim"])
def test_community_admission_module_off_retains_requests_and_on_restores_capacity(kind, settings):
    settings.MANAGED_PLANS_ENABLED = False
    w = member_world(kind)
    saved = w[0].enabled_modules
    w[0].enabled_modules = [key for key in saved if key != "membership"]
    w[0].save(update_fields=["enabled_modules"])
    before = snapshot()
    with pytest.raises(APIException) as failure:
        admit(w, kind, 0)
    assert (failure.value.status_code, str(failure.value.detail["code"])) == (404, "module_disabled")
    assert snapshot() == before
    w[0].enabled_modules = saved
    w[0].save(update_fields=["enabled_modules"])
    admit(w, kind, 0)
    assert _COUNTERS["members"](w[0]) == w[4] + 1


@pytest.mark.parametrize("kind", STAFF_KINDS)
def test_staff_admission_is_independent_of_community_and_payments_modules(kind, settings, monkeypatch):
    settings.MANAGED_PLANS_ENABLED = False
    w = staff_world(kind, monkeypatch)
    w[0].enabled_modules = [key for key in w[0].enabled_modules if key not in {"membership", "payments"}]
    w[0].save(update_fields=["enabled_modules"])
    staff_admit(w, kind, 0)
    assert _COUNTERS["staff"](w[0]) == w[4] + 1
    assert Payment.objects.filter(makerspace=w[0]).count() == 0
