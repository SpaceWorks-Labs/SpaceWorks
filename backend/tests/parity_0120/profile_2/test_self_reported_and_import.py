"""Self-reported achievements CRUD and importing ONLY the caller's own submission."""
from datetime import date, timedelta

import pytest

from apps.audit.models import AuditLog
from apps.makerspaces.account_profile import account_profile_for
from apps.makerspaces.models import ProfileAchievement

from .conftest import client_for

pytestmark = pytest.mark.django_db
URL = "/api/v1/member/profile/achievements"


def test_crud_is_owner_scoped_and_audited_without_content(ada, grace):
    client = client_for(ada)
    created = client.post(URL, {"title": "Won a thing", "url": "https://example.test/x"}, format="json")
    assert created.status_code == 201
    pk = created.data["id"]
    assert client.patch(f"{URL}/{pk}", {"issuer": "Club"}, format="json").status_code == 200
    assert client_for(grace).patch(f"{URL}/{pk}", {"issuer": "Hack"}, format="json").status_code == 404
    assert client.delete(f"{URL}/{pk}").status_code == 204
    rows = AuditLog.objects.filter(actor=ada)
    assert {"member.profile_achievement_created", "member.profile_achievement_updated",
            "member.profile_achievement_deleted"} <= set(rows.values_list("action", flat=True))
    assert "Won a thing" not in str(list(rows.values_list("meta", flat=True)))


def test_validation_https_future_date_and_cap(ada):
    client = client_for(ada)
    assert client.post(URL, {"title": "x", "url": "http://insecure.test"}, format="json").status_code == 400
    future = (date.today() + timedelta(days=3)).isoformat()
    assert client.post(URL, {"title": "x", "achieved_on": future}, format="json").status_code == 400
    profile = account_profile_for(ada)
    ProfileAchievement.objects.bulk_create([ProfileAchievement(profile=profile, title=f"t{i}") for i in range(30)])
    assert client.post(URL, {"title": "one too many"}, format="json").status_code == 400


# Importing a submission is covered against real hackathon submissions in test_real_results.py.
