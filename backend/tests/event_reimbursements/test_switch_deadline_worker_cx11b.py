"""CX11B: retained awards/pools are untouched off and deadline work resumes on."""
from datetime import timedelta

import pytest
from django.db import connection
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.event_reimbursements import award_workflow
from apps.event_reimbursements.models import GrantAward
from apps.event_reimbursements.tasks import sweep_deadlines_task
from tests.event_reimbursements.conftest import cmd
from tests.event_reimbursements.helpers import requested
from tests.modules.test_switch_matrix_objects_rest_support import _no_write, domain_rows, switch

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.mark.parametrize("key", ["events", "event_reimbursements"])
def test_deadline_worker_does_nothing_off_then_releases_the_same_award_once(world, monkeypatch, key):
    grant = requested(world)
    award_workflow.decide(request=world.finance, event_id=world.event.pk, request_id=grant.pk,
        data=cmd(grant.version, outcome="award", amount_minor=10000, currency="INR", reason_code="need_based",
            expected_award_version=None, expected_pool_version=world.pool.version))
    award = GrantAward.objects.get(request=grant)
    monkeypatch.setattr(timezone, "now", lambda: award.accept_by + timedelta(seconds=1))
    original = switch(world.space, key)
    before = domain_rows()
    with connection.execute_wrapper(_no_write):
        assert sweep_deadlines_task() == 0
    assert domain_rows() == before
    switch(world.space, key, original=original)
    assert sweep_deadlines_task() == 1
    award.refresh_from_db(); world.pool.refresh_from_db()
    assert (award.state, world.pool.reserved_minor, world.pool.committed_minor) == ("expired", 0, 0)
    assert world.pool.entries.filter(kind="release").count() == 1
    assert AuditLog.objects.filter(action="event.reimbursement.forfeited", target_id=str(award.pk)).count() == 1
    after = domain_rows()
    assert sweep_deadlines_task() == 0
    assert domain_rows() == after
