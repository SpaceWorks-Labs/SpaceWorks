"""Open-by-default profile (303) and the 404 matrix per audience."""
import pytest
from django.utils import timezone

from apps.makerspaces.account_profile import account_profile_for, save_profile
from apps.makerspaces.models import AccountProfile, PublicHandle
from apps.audit.models import AuditLog

from .conftest import client_for, make_person

pytestmark = pytest.mark.django_db
READ = "/api/v1/public/profiles/{}/"


def test_new_profile_defaults_open_signed_in_closed_web(ada):
    profile = account_profile_for(ada)
    assert profile.is_visible is True
    assert all(getattr(profile, name) for name in (
        "show_status", "show_about", "show_experience", "show_education", "show_achievements",
        "show_projects", "show_skills", "show_links", "show_interests", "show_events", "show_spaces"))
    assert profile.public_visible is False and profile.public_consented_at is None


def test_signed_in_reads_without_consent_logged_out_does_not(ada, grace):
    account_profile_for(ada)
    handle = PublicHandle.objects.get(user=ada).handle
    assert client_for(grace).get(READ.format(handle)).status_code == 200
    assert client_for().get(READ.format(handle)).status_code == 404


def test_logged_out_reads_after_fresh_consent(ada):
    account_profile_for(ada)
    handle = PublicHandle.objects.get(user=ada).handle
    with pytest.raises(Exception):
        save_profile(ada, {"public_visible": True})  # no publication_consent -> refused
    save_profile(ada, {"public_visible": True, "publication_consent": True})
    response = client_for().get(READ.format(handle))
    assert response.status_code == 200 and response.data["audience"] == "public"
    assert "toggles" not in response.data and "public_consented_at" not in response.data


def test_hidden_missing_restricted_are_the_same_404(ada, grace, stranger):
    account_profile_for(ada)
    handle = PublicHandle.objects.get(user=ada).handle
    save_profile(ada, {"is_visible": False})
    hidden = client_for(grace).get(READ.format(handle))
    missing = client_for(grace).get("/api/v1/public/profiles/no-such-person/")
    assert hidden.status_code == missing.status_code == 404
    assert hidden.json() == missing.json()
    save_profile(ada, {"is_visible": True})
    ada.access_status = ada.AccessStatus.RESTRICTED
    ada.save(update_fields=["access_status"])
    assert client_for(grace).get(READ.format(handle)).status_code == 404


def test_owner_sees_switches_other_sees_gated_sections(ada, grace):
    account_profile_for(ada)
    save_profile(ada, {"bio": "Maker of engines", "show_about": False})
    handle = PublicHandle.objects.get(user=ada).handle
    owner = client_for(ada).get(READ.format(handle)).data
    other = client_for(grace).get(READ.format(handle)).data
    assert owner["audience"] == "owner" and owner["bio"] == "Maker of engines" and "toggles" in owner
    assert other["audience"] == "member" and other["bio"] == "" and other["shown"]["about"] is False


def test_by_account_link_works_signed_in_only(ada, grace):
    account_profile_for(ada)
    url = f"/api/v1/profiles/by-account/{ada.pk}/"
    assert client_for(grace).get(url).status_code == 200
    assert client_for().get(url).status_code in (401, 404)


def test_section_toggle_change_is_audited_without_content(ada):
    account_profile_for(ada)
    save_profile(ada, {"bio": "secret words", "show_links": False, "is_visible": False})
    meta = AuditLog.objects.filter(action="member.profile_updated", actor=ada).latest("created_at").meta
    assert meta["visibility_changed"] is True and meta["sections_changed"] == ["show_links"]
    assert "secret words" not in str(meta)


def test_status_note_cap_and_preset(ada):
    response = client_for(ada).put("/api/v1/member/profile", {"status": "student", "status_note": "x" * 121}, format="json")
    assert response.status_code == 400
    ok = client_for(ada).put("/api/v1/member/profile", {"status": "student", "status_note": "Finals"}, format="json")
    assert ok.status_code == 200 and ok.data["status"] == {"preset": "student", "note": "Finals"}
