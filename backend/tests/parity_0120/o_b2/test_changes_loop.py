"""O-B2: ask an applicant for changes -- one round, scoped, audited, notified; resubmission returns to the queue."""
import pytest
from django.urls import reverse
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.audit.models import AuditLog
from apps.makerspaces import member_unit_assign as assign
from apps.makerspaces import membership_admission_changes as changes
from apps.makerspaces import membership_services
from apps.makerspaces.membership_admission_settings import AdmissionError
from apps.makerspaces.models import MembershipRequest
from tests.makerspaces.l4_helpers import features_off, features_on
from tests.makerspaces.test_membership_admission_matrix import _application, _setup
from tests.makerspaces.test_membership_j1 import user

pytestmark = pytest.mark.django_db(transaction=True)


def _open_application(**overrides):
    space, actor, applicant, plan, _ = _setup("approval", **overrides)
    features_on(space, "ask_changes")
    return space, actor, applicant, _application(space, applicant)


def test_changes_can_be_asked_once_and_resubmission_returns_to_the_queue():
    space, actor, applicant, row = _open_application()
    sent = changes.request_changes(actor, row, "  Please explain your skills.  ")
    assert sent.state == "changes_requested" and sent.changes_rounds == 1 and sent.changes_note == "Please explain your skills."
    assert sent.expires_at > row.created_at
    back = changes.resubmit(applicant, sent, {})
    assert back.state == "requested"
    with pytest.raises(AdmissionError) as error:
        changes.request_changes(actor, back, "Again")
    assert error.value.detail["code"] == "membership_changes_already_asked"
    actions = set(AuditLog.objects.filter(makerspace=space).values_list("action", flat=True))
    assert {"membership.changes_requested", "membership.request_resubmitted"} <= actions


def test_only_requested_or_awaiting_vouches_can_be_sent_back_and_a_reason_is_required():
    space, actor, applicant, row = _open_application()
    with pytest.raises(ValidationError):
        changes.request_changes(actor, row, "   ")
    row.state = "awaiting_payment"
    row.save(update_fields=["state"])
    with pytest.raises(AdmissionError) as error:
        changes.request_changes(actor, row, "Nope")
    assert error.value.detail["code"] == "membership_changes_not_allowed"


def test_a_request_waiting_for_changes_cannot_be_approved_but_can_be_declined():
    space, actor, applicant, row = _open_application()
    sent = changes.request_changes(actor, row, "Fix it")
    from apps.makerspaces.membership_helpers import _member_role
    with pytest.raises(AdmissionError):
        membership_services.approve_request(actor, sent, _member_role(space))
    declined = membership_services.revoke_request(actor, sent, "No")
    assert declined.state == "revoked"


def test_only_the_applicant_resubmits_and_only_while_changes_are_requested():
    space, actor, applicant, row = _open_application()
    with pytest.raises(AdmissionError) as error:
        changes.resubmit(applicant, row, {})
    assert error.value.detail["code"] == "membership_resubmit_not_allowed"
    sent = changes.request_changes(actor, row, "Fix it")
    with pytest.raises(PermissionDenied):
        changes.resubmit(user("ob2-someone-else"), sent, {})


def test_ask_changes_off_blocks_new_asks_but_never_strands_a_waiting_applicant():
    space, actor, applicant, row = _open_application()
    sent = changes.request_changes(actor, row, "Fix it")
    features_off(space, "ask_changes")
    assert changes.resubmit(applicant, sent, {}).state == "requested"
    other_space, other_actor, other_applicant, other = _open_application()
    features_off(other_space, "ask_changes")
    from apps.makerspaces.guards import SurfaceOff
    with pytest.raises(SurfaceOff):
        changes.request_changes(other_actor, other, "Fix it")


def test_a_unit_scoped_lead_cannot_send_back_a_request_outside_their_unit():
    from tests.parity_0120.o_b1.helpers import lead, tree, units_space
    from apps.makerspaces.models_member_units import MembershipRequestUnit
    space, boss = units_space("ob2-changes-scope")
    features_on(space, "ask_changes")
    south, kochi, north = tree(boss, space)
    scoped_actor, staff_row = lead(space, "ob2-scoped-lead")
    assign.set_staff_unit_scope(boss, staff_row, south.pk)
    applicant = user("ob2-scope-applicant")
    membership_services.request_membership(applicant, space)
    row = MembershipRequest.objects.get(makerspace=space, user=applicant)
    MembershipRequestUnit.objects.create(makerspace=space, request=row, unit=north)
    from django.http import Http404
    with pytest.raises(Http404):
        changes.request_changes(scoped_actor, row, "Fix it")
    MembershipRequestUnit.objects.filter(request=row).update(unit=kochi)
    assert changes.request_changes(scoped_actor, row, "Fix it").state == "changes_requested"


def test_the_admin_and_member_routes_round_trip():
    from rest_framework.test import APIClient
    from tests.accounts.reauth_helpers import force_recent_authenticate
    space, actor, applicant, row = _open_application()
    staff = APIClient()
    force_recent_authenticate(staff, actor)
    url = reverse("admin-membership-request-changes", args=[space.pk, row.pk])
    response = staff.post(url, {"reason": "More detail"}, format="json")
    assert response.status_code == 200 and response.json()["state"] == "changes_requested"
    own = APIClient()
    own.force_authenticate(applicant)
    done = own.patch(reverse("membership-request-resubmit", args=[row.pk]), {"application_answers": {}}, format="json")
    assert done.status_code == 200 and done.json()["state"] == "requested"
    stranger = APIClient()
    stranger.force_authenticate(user("ob2-stranger"))
    assert stranger.patch(reverse("membership-request-resubmit", args=[row.pk]), {}, format="json").status_code == 404
