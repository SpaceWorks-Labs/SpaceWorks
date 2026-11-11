"""O-B1: unit preselect precedence, plan/unit restriction, request-to-membership unit copy, import verify mode."""
import pytest

from apps.makerspaces import member_unit_assign as assign
from apps.makerspaces import membership_invite_links as links
from apps.makerspaces.membership_admission_settings import AdmissionError
from apps.makerspaces.membership_join_units import apply_request_unit, record_request_unit, resolve_join_unit
from apps.makerspaces.models import ImportedMember, MembershipRequest, MembershipUnit
from apps.makerspaces.models_member_units import ImportedMemberUnit, PlanUnit
from tests.makerspaces.l4_helpers import features_off, plan
from tests.makerspaces.test_membership_j1 import user
from tests.parity_0120.o_b1.helpers import community_member, tree, units_space

pytestmark = pytest.mark.django_db(transaction=True)


def test_explicit_code_beats_the_invite_unit_which_beats_the_existing_unit():
    space, boss = units_space("ob1-join-precedence")
    south, kochi, north = tree(boss, space)
    member = community_member(space, "ob1-join-member")
    assign.assign_member_unit(boss, member, north.pk)
    link, code = links.create_link(boss, space, unit_id=kochi.pk)
    assert resolve_join_unit(space, member.user, None, "south", code).pk == south.pk
    assert resolve_join_unit(space, member.user, None, None, code).pk == kochi.pk
    assert resolve_join_unit(space, member.user, None, None, None).pk == north.pk
    assert resolve_join_unit(space, user("ob1-join-stranger"), None, None, None) is None
    assert link.unit_id == kochi.pk


def test_unknown_or_archived_code_is_a_typed_error_and_off_means_inert():
    space, boss = units_space("ob1-join-invalid")
    _south, _kochi, north = tree(boss, space)
    person = user("ob1-join-person")
    with pytest.raises(AdmissionError) as error:
        resolve_join_unit(space, person, None, "NOPE", None)
    assert error.value.detail["code"] == "membership_unit_invalid"
    features_off(space, "unit_scoped_staff", "units")
    assert resolve_join_unit(space, person, None, "NORTH", None) is None


def test_a_plan_limited_to_units_needs_a_unit_inside_them():
    space, boss = units_space("ob1-join-plan")
    south, kochi, north = tree(boss, space)
    southern = plan(space, "Southern")
    PlanUnit.objects.create(makerspace=space, plan=southern, unit=south)
    person = user("ob1-join-plan-person")
    with pytest.raises(AdmissionError) as error:
        resolve_join_unit(space, person, southern, None, None)
    assert error.value.detail["code"] == "membership_unit_required"
    with pytest.raises(AdmissionError) as error:
        resolve_join_unit(space, person, southern, "NORTH", None)
    assert error.value.detail["code"] == "membership_unit_not_allowed"
    assert resolve_join_unit(space, person, southern, "KOCHI", None).pk == kochi.pk
    assert north.pk  # sibling stays outside


def test_the_chosen_unit_is_copied_to_the_membership_on_activation():
    space, boss = units_space("ob1-join-copy")
    _south, kochi, _north = tree(boss, space)
    member = community_member(space, "ob1-join-copy-member")
    request = MembershipRequest.objects.create(makerspace=space, user=member.user, kind="request",
                                               state="requested", invite_email=member.user.email)
    record_request_unit(request, kochi)
    assert apply_request_unit(member, request, boss).unit_id == kochi.pk
    assert MembershipUnit.objects.get(membership=member).unit_id == kochi.pk
    assert apply_request_unit(member, request, boss) is None  # never overwrites a placement


def test_import_verify_mode_holds_rows_until_the_lead_approves():
    from apps.admin_api import bulk_import_members_units as reviews
    space, boss = units_space("ob1-import")
    _south, kochi, _north = tree(boss, space)
    unit = reviews.resolve_import_unit(boss, space, kochi.pk, True)
    imported = ImportedMember.objects.create(makerspace=space, email="held@example.test",
                                             status=ImportedMember.Status.RECORD_ONLY)
    reviews.attach_unit(imported, unit, True)
    row = ImportedMemberUnit.objects.get(imported=imported)
    assert row.review_status == "pending" and imported.invitation_id is None
    reviews.reject_review(boss, space, imported.pk)
    imported.refresh_from_db()
    assert imported.status == ImportedMember.Status.CANCELLED
    with pytest.raises(Exception):
        reviews.approve_review(boss, space, imported.pk)  # no longer pending
