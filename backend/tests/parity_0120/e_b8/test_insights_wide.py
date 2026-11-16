"""E-B8: wider superadmin insights are counts only: no bodies, subjects, tokens, secrets or addresses."""
import json

import pytest

from apps.apiclients.models import ApiClient
from tests.audit_explorer_helpers import superadmin
from tests.return_helpers import authenticated_client, make_member, make_space

pytestmark = pytest.mark.django_db


def test_insights_carry_activity_security_and_storage_as_counts():
    make_space("eb8-insights")
    client = ApiClient.objects.create(label="Reporting", client_id="ck_eb8", secret_encrypted=b"ciphertext-bytes")
    body = authenticated_client(superadmin("eb8-insights-root")).get("/api/v1/admin/platform/insights/").json()
    assert set(body) >= {"activity", "security", "storage", "growth", "outbox"}
    assert body["security"]["api_clients"]["active"] >= 1
    assert {row["action"] for row in body["security"]["sensitive_actions"]} >= {"auth.mfa_reset", "api_client.revoked"}
    assert body["storage"]["spaces"] >= 1
    text = json.dumps(body)
    for forbidden in (client.client_id, "ciphertext", "secret_encrypted", "subject"):
        assert forbidden not in text
    for row in (body["activity"] or {}).get("recent_broadcasts", []):
        assert set(row) == {"completed_at", "audience_statuses", "audience_attendance"}


def test_insights_stay_superadmin_only():
    staff = authenticated_client(make_member("eb8-insights-sm", make_space("eb8-insights-2")))
    assert staff.get("/api/v1/admin/platform/insights/").status_code in (401, 403)
