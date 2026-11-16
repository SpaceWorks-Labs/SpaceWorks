"""Existing quote approval honours charge switches independently of the online rail (184 G3)."""
from decimal import Decimal

import pytest

from apps.machines import service_workflow_review as review
from apps.machines.models import MachineServiceRequest, MakerspaceMachineTypePolicy
from apps.payments.models import Payment
from tests.machines.eta_helpers import job
from tests.machines.member_support_cx11b_g2 import member_world
from tests.machines.route_support_cx11b_g2 import actions, command, domain_rows, no_domain_writes, response_pair, toggle
from tests.machines.test_job_flow import priced
from tests.modules.test_switch_matrix_objects_rest_isolation import rolled_back

pytestmark = [pytest.mark.django_db, pytest.mark.area_machines, pytest.mark.area_machine_service]


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("key", ["charges.enabled", "charges.machines", "payments", "machines.job_quotes"])
def test_prepay_approval_creates_exact_frozen_debt_or_queues_free_and_retains_existing_money(native, key):
    w = priced(member_world(native))
    MakerspaceMachineTypePolicy.objects.create(makerspace=w.space, machine_type=w.kind, payment_timing="prepay")
    row = review.send_quote(job(w, member=w.member), w.actor, estimated_minutes=30)
    assert Decimal(row.quote_snapshot["total"]) == Decimal("65")

    def call(client):
        return command(client, "member-machine-job-approve-quote", "post", [row.pk], {"digest": row.quote_digest})

    def answer(*, free=False):
        before = actions()
        response = call(w.client)
        assert response_pair(response) == (200, None)
        saved = MachineServiceRequest.objects.get(pk=row.pk)
        assert (saved.status, saved.prepay, saved.quote_digest) == ("accepted" if free else "quoted", True, row.quote_digest)
        assert saved.quote_approved_at is not None
        if free:
            assert not Payment.objects.filter(subject_type="machine_service_request", subject_id=row.pk).exists()
        else:
            payment = Payment.objects.get(subject_type="machine_service_request", subject_id=row.pk)
            assert (payment.member_id, payment.amount, payment.currency, payment.status, payment.provider) == (
                w.member.pk, Decimal("65"), "usd", "pending", "unclaimed")
            assert payment.pricing_snapshot["digest"] == row.quote_digest
            assert Decimal(payment.pricing_snapshot["total"]) == Decimal("65")
        assert actions()[len(before):] == (["machine_service.quote_approved"] if free else ["payment.created", "payment.document_issued", "machine_service.quote_approved"])

    def outsiders():
        before = domain_rows()
        for client in (w.foreign, w.same_space):
            with no_domain_writes():
                response = call(client)
            # 520 ownership is checked before money policy, in every switch state.
            expected = (403, "permission_denied") if native and client is w.foreign else (404, "not_found")
            assert response_pair(response) == expected, getattr(response, "data", None)
        assert domain_rows() == before

    outsiders()
    with rolled_back():
        answer()
    original = toggle(w.space, key)
    outsiders()
    # These are policy switches: they permit a FREE queue transition, or keep
    # recording a debt without a rail. They do not disable the approval endpoint.
    with rolled_back():
        answer(free=key.startswith("charges."))
    toggle(w.space, key, original)
    outsiders()
    answer()
    retained = domain_rows()
    toggle(w.space, key)
    assert domain_rows() == retained
    toggle(w.space, key, original)
    assert domain_rows() == retained
