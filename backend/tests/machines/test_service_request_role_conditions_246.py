"""Decision 246: machine service-request decisions across every built-in role, replay and isolation.

Accepting or rejecting a job needs machine authority (`manage_machines`, and for a Machine Manager the
linked machine type). Expectations are derived from `ROLE_CATALOG`. A refused call leaves the job pending;
a decided job is decided once, so a second accept or reject is a state conflict and writes no extra audit.
"""
import pytest
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.machines.models import MachineServiceRequest
from apps.makerspaces.role_catalog import ROLE_BY_SLUG, ROLE_CATALOG
from tests.fixed_roles.helpers import staff_account
from tests.machines.eta_helpers import job, world
from tests.return_helpers import authenticated_client

pytestmark = pytest.mark.django_db
SLUGS = [role.slug for role in ROLE_CATALOG]
BASE = "/api/v1/admin/machine-service/requests"


def _allowed(slug):
    return "manage_machines" in ROLE_BY_SLUG[slug].granted_actions


def _actor(w, slug, tag):
    return staff_account(w.space, f"msr-{tag}-{slug}", slug, machine_types=(w.kind,))


@pytest.mark.parametrize("decision", ["accept", "reject"])
@pytest.mark.parametrize("slug", SLUGS)
def test_decision_follows_manage_machines_for_every_built_in_role(slug, decision):
    w = world(f"msr-{decision}-{slug}".replace("_", "-"))
    request = job(w)
    body = {} if decision == "accept" else {"reason": "Out of scope"}
    response = authenticated_client(_actor(w, slug, decision)).post(f"{BASE}/{request.pk}/{decision}", body,
                                                                    format="json")
    request.refresh_from_db()
    if _allowed(slug):
        assert response.status_code == 200, response.content
        assert request.status == ("accepted" if decision == "accept" else "rejected")
        assert AuditLog.objects.filter(makerspace=w.space, target_id=str(request.pk)).exists()
    else:
        assert response.status_code in (403, 404)
        assert request.status == MachineServiceRequest.Status.PENDING
        # Submitting the job audits `machine_service.submitted` (the member's own act);
        # the refused decision must add nothing beyond it.
        assert not AuditLog.objects.filter(makerspace=w.space, action__startswith="machine_service",
                                           target_id=str(request.pk)).exclude(
            action="machine_service.submitted").exists()


def test_a_decided_job_cannot_be_accepted_or_rejected_again():
    w = world("msr-replay")
    request = job(w)
    boss = authenticated_client(staff_account(w.space, "msr-replay-boss", "space_manager"))
    assert boss.post(f"{BASE}/{request.pk}/accept", {}, format="json").status_code == 200
    again = boss.post(f"{BASE}/{request.pk}/accept", {}, format="json")
    flipped = boss.post(f"{BASE}/{request.pk}/reject", {"reason": "Changed mind"}, format="json")
    assert again.status_code in (400, 409) and flipped.status_code in (400, 409)
    request.refresh_from_db()
    assert request.status == "accepted"
    assert AuditLog.objects.filter(makerspace=w.space, target_id=str(request.pk), action__endswith="accepted").count() <= 1


@pytest.mark.parametrize("body", [{"estimated_minutes": -5}, {"estimated_minutes": "soon"}, {"planned_grams": -1}])
def test_accept_validation_rejects_negative_or_malformed_estimates(body):
    w = world("msr-valid")
    request = job(w)
    boss = authenticated_client(staff_account(w.space, "msr-valid-boss", "space_manager"))
    assert boss.post(f"{BASE}/{request.pk}/accept", body, format="json").status_code in (400, 409, 422)
    request.refresh_from_db()
    assert request.status == MachineServiceRequest.Status.PENDING


def test_a_job_of_another_space_is_404_for_every_action_and_anonymous_is_refused():
    w, other = world("msr-iso-a"), world("msr-iso-b")
    request = job(w)
    outsider = authenticated_client(staff_account(other.space, "msr-iso-out", "space_manager"))
    for action, body in (("accept", {}), ("reject", {"reason": "x"}), ("start", {}), ("cancel", {})):
        assert outsider.post(f"{BASE}/{request.pk}/{action}", body, format="json").status_code in (403, 404)
    assert outsider.get(f"{BASE}/{request.pk}").status_code in (403, 404)
    anon = APIClient()
    assert anon.post(f"{BASE}/{request.pk}/accept", {}, format="json").status_code in (401, 403)
    request.refresh_from_db()
    assert request.status == MachineServiceRequest.Status.PENDING


def test_a_machine_manager_without_the_machine_type_link_reaches_nothing():
    w = world("msr-scope")
    request = job(w)
    unlinked = staff_account(w.space, "msr-scope-mm", "machine_manager")
    response = authenticated_client(unlinked).post(f"{BASE}/{request.pk}/accept", {}, format="json")
    assert response.status_code in (403, 404)
    request.refresh_from_db()
    assert request.status == MachineServiceRequest.Status.PENDING


def test_starting_or_completing_a_job_that_is_not_accepted_is_a_conflict():
    w = world("msr-edge")
    request = job(w)
    boss = authenticated_client(staff_account(w.space, "msr-edge-boss", "space_manager"))
    for action in ("start", "complete"):
        assert boss.post(f"{BASE}/{request.pk}/{action}", {}, format="json").status_code in (400, 409)
    request.refresh_from_db()
    assert request.status == MachineServiceRequest.Status.PENDING
