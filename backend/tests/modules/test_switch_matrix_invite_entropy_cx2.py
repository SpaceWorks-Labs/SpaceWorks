"""Real invite probes keep the reviewed success triple without relaxing error contracts."""
import copy
import json
import secrets

import pytest

from apps.audit.models import AuditLog
from apps.makerspaces import membership_invite_links
from apps.makerspaces.models import MembershipInviteLink
from tests.modules.switch_matrix_helpers import (
    INVITE_LINK_TEST_CODE, MODULE_KEYS, fill, live_space, probe, root_client,
)
from tests.modules.test_switch_matrix_contract import SNAPSHOT_PATH, validate_snapshot
from tests.modules.test_switch_matrix_on_responses import REVIEWED_ON, assert_reviewed_on

pytestmark = [pytest.mark.django_db, pytest.mark.area_membership]
ROUTE = ("POST", "/api/v1/admin/makerspaces/<int:makerspace_id>/membership-invite-links")
IDENTITY = " ".join(ROUTE)
EXPECTED = (201, "ieVwjt8B6jpCb9j3l6mkqa_f", None)


def test_two_real_invite_probes_keep_reviewed_triple_and_roll_back_link_and_audit(monkeypatch):
    client, space = root_client(verified=True), live_space("invite-entropy", MODULE_KEYS)
    url = fill(ROUTE[1], space)
    original_post = client.post
    real_entropy, real_secrets = secrets.token_urlsafe, membership_invite_links.secrets
    before = MembershipInviteLink.objects.count(), AuditLog.objects.count()
    observed = []

    def observe_post(*args, **kwargs):
        response = original_post(*args, **kwargs)
        assert (response.status_code, response.data.get("code")) == EXPECTED[:2], response.data
        # Observe the actual service's writes before probe() rolls the savepoint back.
        link = MembershipInviteLink.objects.get(pk=response.data["id"], makerspace=space)
        assert (link.code_digest, link.label, link.max_uses, link.uses, link.created_by_id) == (
            membership_invite_links.code_digest(INVITE_LINK_TEST_CODE), "Reviewed invite", 2, 0,
            client.handler._force_user.pk,
        )
        audit = AuditLog.objects.get(makerspace=space, action="membership.invite_link_created",
                                     target_id=str(link.pk))
        assert (audit.actor_id, audit.target_type, audit.meta) == (
            link.created_by_id, "makerspaces.membershipinvitelink",
            {"link_id": link.pk, "plan_id": None, "max_uses": 2, "unit_id": None},
        )
        assert (MembershipInviteLink.objects.count(), AuditLog.objects.count()) == (before[0] + 1, before[1] + 1)
        assert secrets.token_urlsafe is real_entropy
        observed.append(response.data["code"])
        return response

    monkeypatch.setattr(client, "post", observe_post)
    results = []
    for _ in range(2):
        results.append(probe(client, "POST", url, body={"label": "Reviewed invite", "max_uses": 2}))
        assert_reviewed_on(ROUTE, results[-1])
        assert (MembershipInviteLink.objects.count(), AuditLog.objects.count()) == before
        assert membership_invite_links.secrets is real_secrets
        assert secrets.token_urlsafe is real_entropy
    assert results == [EXPECTED, EXPECTED]
    assert observed == [INVITE_LINK_TEST_CODE, INVITE_LINK_TEST_CODE]
    assert REVIEWED_ON[IDENTITY] == EXPECTED
    snapshot = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    candidate = copy.deepcopy(snapshot)
    candidate["base"][IDENTITY] = list(results[-1])
    validate_snapshot(candidate, snapshot)


def test_invalid_invite_probe_keeps_real_serializer_refusal_and_strict_reviewed_contract(monkeypatch):
    client, space = root_client(verified=True), live_space("invite-invalid", MODULE_KEYS)
    before = MembershipInviteLink.objects.count(), AuditLog.objects.count()
    original_post = client.post

    def observe_post(*args, **kwargs):
        response = original_post(*args, **kwargs)
        # Decision 481 preserves DRF field-keyed validation bodies without a top-level code.
        assert response.status_code == 400
        assert set(response.data) == {"max_uses"}
        assert [error.code for error in response.data["max_uses"]] == ["min_value"]
        return response

    monkeypatch.setattr(client, "post", observe_post)
    response = probe(client, "POST", fill(ROUTE[1], space), body={"max_uses": 0})
    assert response == (400, None, None)
    assert (MembershipInviteLink.objects.count(), AuditLog.objects.count()) == before
    with pytest.raises(AssertionError):
        assert_reviewed_on(ROUTE, response)
    snapshot = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    candidate = copy.deepcopy(snapshot)
    candidate["base"][IDENTITY] = list(response)
    with pytest.raises(ValueError, match="reviewed on response changed"):
        validate_snapshot(candidate, snapshot)


@pytest.mark.parametrize("wrong", [
    (401, "not_authenticated", None), (403, "permission_denied", None),
    (404, "not_found", None), (405, "method_not_allowed", None),
    (500, "server_error", None), (201, "unexpected_code", None),
    (200, EXPECTED[1], None),
])
def test_invite_contract_still_rejects_wrong_status_or_code(wrong):
    with pytest.raises(AssertionError) as caught:
        assert_reviewed_on(ROUTE, wrong)
    assert type(caught.value) is AssertionError
    # Pytest appends its comparison explanation to the authored assertion message.
    assert str(caught.value).split("\n", 1)[0] == repr((IDENTITY, wrong, EXPECTED))
    snapshot = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    candidate = copy.deepcopy(snapshot)
    candidate["base"][IDENTITY] = list(wrong)
    problems = []
    if wrong[0] >= 500:
        problems.append(("base", IDENTITY, list(wrong)))
    problems.extend([
        (IDENTITY, "reviewed on response changed or unreviewed", EXPECTED, list(wrong)),
        (IDENTITY, "previous reviewed on response changed", list(EXPECTED)),
    ])
    with pytest.raises(ValueError) as rejected:
        validate_snapshot(candidate, snapshot)
    assert type(rejected.value) is ValueError
    assert str(rejected.value) == "Snapshot contradicts switch contracts: " + repr(problems)
    assert snapshot["base"][IDENTITY] == list(EXPECTED)

