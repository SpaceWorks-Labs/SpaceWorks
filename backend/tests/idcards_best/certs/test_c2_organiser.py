"""C2: organiser thank-you certificates for approved co-organisers."""
import pytest

from apps.events.contributions.models_roles import EventRoleAssignment
from apps.events.credentials.errors import ProgrammeConflict
from apps.tenant_migration.semantic_certificate_proof import remap_contribution_proof
from tests.events.checkin_helpers import make_member

from .helpers import ended_event, issue

pytestmark = pytest.mark.django_db(transaction=True)


def _organiser(slug, state="approved"):
    space, event = ended_event(slug)
    member = make_member(space, "organiser", display_name="Grace Hopper")
    role = EventRoleAssignment.objects.create(event=event, makerspace=space, member=member,
                                              role="co_organizer", origin="staff", state=state)
    return event, member, role


def test_approved_co_organiser_receives_an_organiser_certificate():
    event, member, role = _organiser("c2-organiser")
    row = issue(event, "role_assignment", role.pk, kind="organiser_thanks")
    assert row.kind == "organiser_thanks" and row.recipient_member_id == member.pk
    assert row.layout_snapshot["contribution_proof"] == {"version": 1, "role_assignment_id": role.pk,
                                                         "role": "co_organizer"}
    assert row.layout_snapshot["merge"] == {"kind": "Organiser", "award": "", "role": "Organiser", "place": ""}


def test_organiser_kind_must_match_the_role_and_needs_approval():
    event, member, role = _organiser("c2-mismatch")
    with pytest.raises(ProgrammeConflict):
        issue(event, "role_assignment", role.pk, kind="mentor_thanks")
    event, member, role = _organiser("c2-proposed", state="proposed")
    with pytest.raises(ProgrammeConflict):
        issue(event, "role_assignment", role.pk, kind="organiser_thanks")


def test_revoked_organiser_role_makes_the_proof_stale():
    from apps.events.certificates.contribution_proof import require_current
    event, member, role = _organiser("c2-stale")
    row = issue(event, "role_assignment", role.pk, kind="organiser_thanks")
    EventRoleAssignment.objects.filter(pk=role.pk).update(state="revoked")
    with pytest.raises(ProgrammeConflict):
        require_current(row)


def test_portable_organiser_proof_remaps_the_role():
    proof = {"version": 1, "role_assignment_id": 7, "role": "co_organizer"}
    value = remap_contribution_proof({"contribution_proof": proof}, lambda model, pk: pk + 10)
    assert value["contribution_proof"]["role_assignment_id"] == 17
    with pytest.raises(ValueError):
        remap_contribution_proof({"contribution_proof": {**proof, "evidence": [1]}}, lambda model, pk: pk)
