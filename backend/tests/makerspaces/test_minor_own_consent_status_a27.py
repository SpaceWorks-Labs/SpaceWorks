"""Open item A27 (PE7): a minor reads their own guardian-consent standing, and nothing else."""
import pytest
from rest_framework.test import APIClient

from apps.makerspaces import minors
from tests.makerspaces.l4_helpers import features_off
from tests.makerspaces.test_membership_j1 import user
from tests.makerspaces.test_minors_consent import _record, _setup, _sign

pytestmark = pytest.mark.django_db(transaction=True)


def _get(actor, makerspace):
    client = APIClient()
    client.force_authenticate(actor)
    return client.get(f"/api/v1/member/makerspaces/{makerspace.pk}/my-guardian-consent")


def test_pending_then_current_then_expired_after_revoke():
    makerspace, staff, child = _setup("a27-states")
    profile = _record(makerspace, staff, child, guardian_email="parent@example.test")
    pending = _get(child, makerspace)
    assert pending.status_code == 200
    assert pending.data["applies"] is True and pending.data["state"] == "pending"
    assert pending.data["guardian_named"] is True
    assert "parent@example.test" not in str(pending.data)
    consent = _sign(profile, staff)
    current = _get(child, makerspace).data
    assert current["state"] == "current" and current["valid_until"] is not None
    minors.revoke_consent(staff, consent)
    assert _get(child, makerspace).data["state"] == "expired"


def test_terms_missing_and_policy_rules_are_reported():
    makerspace, staff, child = _setup("a27-terms", terms=False, minors_may_borrow=True)
    _record(makerspace, staff, child)
    data = _get(child, makerspace).data
    assert data["state"] == "terms_missing"
    assert (data["may_borrow"], data["may_use_machines"]) == (True, False)


def test_an_adult_gets_not_applicable():
    makerspace, _staff, _child = _setup("a27-adult")
    data = _get(user("a27-adult-person"), makerspace).data
    assert (data["applies"], data["state"]) == (False, "not_applicable")


def test_404_while_minors_is_off():
    makerspace, staff, child = _setup("a27-off")
    _record(makerspace, staff, child)
    features_off(makerspace, "minors")
    assert _get(child, makerspace).status_code == 404
