"""E-B6 C17: staff file a travel claim for themselves or for someone else, funded from the event's pool."""
import pytest

from apps.audit.models import AuditLog
from apps.event_reimbursements import award_workflow, staff_claims
from apps.event_reimbursements.models import GrantRequest
from apps.makerspaces.guards import SurfaceOff
from apps.payments.event_payouts.errors import PayoutError
from tests.event_reimbursements.conftest import cmd, make_world, world  # noqa: F401  (fixtures)
from tests.event_reimbursements.helpers import participate

pytestmark = pytest.mark.django_db


def on(world, *extra):
    world.space.enabled_features = sorted(set(world.space.enabled_features) | {"events.staff_claims", *extra})
    world.space.save(update_fields=["enabled_features"])


def claim(world, registration=None, *, amount=10000, **overrides):
    body = {"category": "rail", "amount_minor": amount, "currency": "INR", "note": "Speaker train fare"}
    if registration is not None:
        body["beneficiary_registration_id"] = registration.pk
    return staff_claims.file_claim(request=world.finance, event_id=world.event.pk, data=cmd(0, **body, **overrides))


def test_staff_file_a_claim_on_behalf_of_a_registered_person(world):
    on(world)
    registration = participate(world)
    done = claim(world, registration)
    row = GrantRequest.objects.get(pk=done["id"])
    assert (row.kind, row.state, row.member_id, row.registration_id) == ("staff", "requested", world.owner.pk,
                                                                          registration.pk)
    assert row.estimated_total_minor == 10000 and row.category_estimates[0]["category"] == "rail"
    assert AuditLog.objects.filter(action="event.reimbursement.staff_claim_filed", meta__on_behalf=True).exists()


def test_the_switch_off_answers_not_found(world):
    registration = participate(world)
    with pytest.raises(SurfaceOff):
        claim(world, registration)
    assert not GrantRequest.objects.exists()


def test_a_staff_claim_cannot_exceed_its_pool(world):
    on(world)
    registration = participate(world)
    world.pool.refresh_from_db()
    with pytest.raises(PayoutError) as over:
        claim(world, registration, amount=world.pool.total_minor + 1)
    assert over.value.detail["detail"] and over.value.status_code == 409
    assert not GrantRequest.objects.exists()


def test_a_person_without_a_live_registration_cannot_be_claimed_for(world):
    on(world)
    with pytest.raises(PayoutError) as refused:
        claim(world)  # the filer has no registration of their own on this event
    assert "staff_claim_registration_required" in str(refused.value.detail)


def test_one_request_per_person_per_programme(world):
    on(world)
    registration = participate(world)
    claim(world, registration)
    with pytest.raises(PayoutError) as again:
        staff_claims.file_claim(request=world.finance, event_id=world.event.pk, data=cmd(
            0, category="rail", amount_minor=500, currency="INR", beneficiary_registration_id=registration.pk))
    assert "reimbursement_request_exists" in str(again.value.detail)


def test_finance_decides_a_staff_claim_without_the_participant_rules(world):
    on(world)
    world.programme.eligible_countries = ["IN"]  # a participant with no known country would be refused
    world.programme.save(update_fields=["eligible_countries"])
    registration = participate(world)
    row = GrantRequest.objects.get(pk=claim(world, registration)["id"])
    world.pool.refresh_from_db()
    decided = award_workflow.decide(request=world.finance, event_id=world.event.pk, request_id=row.pk, data=cmd(
        row.version, expected_award_version=None, expected_pool_version=world.pool.version, outcome="award",
        amount_minor=10000, currency="INR", reason_code="need_based"))
    assert decided["state"] == "awarded"
