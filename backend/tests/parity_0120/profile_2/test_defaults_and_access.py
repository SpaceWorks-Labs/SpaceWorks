"""Open-by-default profile (303) and the 404 matrix per audience."""
import pytest
from datetime import datetime, timezone as dt_timezone

from apps.makerspaces.account_profile import account_profile_for, save_profile
from apps.makerspaces.models import AccountProfile, MakerspaceMembership, PublicHandle
from apps.audit.models import AuditLog

from .conftest import client_for, make_person

pytestmark = pytest.mark.django_db
READ = "/api/v1/public/profiles/{}/"


def _profile(user):
    profile = account_profile_for(user)
    MakerspaceMembership.all_tracks.filter(user=user).update(
        activated_at=datetime(2025, 1, 2, 12, tzinfo=dt_timezone.utc))
    return profile


def expected_card(handle):
    # Decision 549 replaces the rich, audience-dependent handle response with this exact card.
    return {"display_name": "Ada", "avatar_url": None, "handle": handle, "bio": "", "projects": [],
            "memberships": [{"slug": slug, "name": slug.title(), "role_title": "Member", "started_on": "2025-01-02"}
                            for slug in ("space-a", "space-b")]}


def test_new_profile_defaults_open_signed_in_closed_web(ada):
    profile = _profile(ada)
    assert profile.is_visible is True
    assert all(getattr(profile, name) for name in (
        "show_status", "show_about", "show_experience", "show_education", "show_achievements",
        "show_projects", "show_skills", "show_links", "show_interests", "show_events", "show_spaces"))
    assert profile.public_visible is False and profile.public_consented_at is None


def test_signed_in_reads_without_consent_logged_out_does_not(ada, grace):
    _profile(ada)
    handle = PublicHandle.objects.get(user=ada).handle
    # Decision 549: signed-in and anonymous readers receive the same public allow-list.
    for viewer in (grace, None):
        response = client_for(viewer).get(READ.format(handle))
        assert response.status_code == 200
        assert response.data == expected_card(handle)


def test_logged_out_reads_after_fresh_consent(ada):
    _profile(ada)
    handle = PublicHandle.objects.get(user=ada).handle
    # Decision 549: retired publication inputs cannot change stored consent or the public card.
    save_profile(ada, {"public_visible": True})
    save_profile(ada, {"public_visible": True, "publication_consent": True})
    response = client_for().get(READ.format(handle))
    assert response.status_code == 200
    assert response.data == expected_card(handle)
    profile = AccountProfile.objects.get(user=ada)
    assert (profile.public_visible, profile.public_consented_at) == (False, None)
    assert "toggles" not in response.data and "public_consented_at" not in response.data


def test_hidden_missing_restricted_are_the_same_404(ada, grace, stranger):
    _profile(ada)
    handle = PublicHandle.objects.get(user=ada).handle
    save_profile(ada, {"is_visible": False})
    hidden = client_for(grace).get(READ.format(handle))
    missing = client_for(grace).get("/api/v1/public/profiles/no-such-person/")
    # Decision 549: a stored opt-out no longer hides the card; unknown handles remain 404.
    assert hidden.status_code == 200
    assert hidden.data == expected_card(handle)
    assert missing.status_code == 404
    assert missing.data["code"] == "not_found"
    save_profile(ada, {"is_visible": True})
    ada.access_status = ada.AccessStatus.RESTRICTED
    ada.save(update_fields=["access_status"])
    restricted = client_for(grace).get(READ.format(handle))
    assert restricted.status_code == 200
    assert restricted.data == {"display_name": "Ada", "avatar_url": None}


def test_owner_sees_switches_other_sees_gated_sections(ada, grace):
    _profile(ada)
    save_profile(ada, {"bio": "Maker of engines", "show_about": False})
    handle = PublicHandle.objects.get(user=ada).handle
    # Decision 549: even the owner sees the section-filtered card on the public URL.
    for viewer in (ada, grace):
        response = client_for(viewer).get(READ.format(handle))
        assert response.status_code == 200
        assert response.data == expected_card(handle)
    # The separate authenticated rich reader retains its owner/section permissions.
    owner = client_for(ada).get(f"/api/v1/profiles/by-account/{ada.pk}/")
    other = client_for(grace).get(f"/api/v1/profiles/by-account/{ada.pk}/")
    assert owner.status_code == other.status_code == 200
    assert owner.data["audience"] == "owner" and owner.data["bio"] == "Maker of engines" and "toggles" in owner.data
    assert other.data["audience"] == "member" and other.data["bio"] == "" and other.data["shown"]["about"] is False


def test_by_account_link_works_signed_in_only(ada, grace):
    _profile(ada)
    url = f"/api/v1/profiles/by-account/{ada.pk}/"
    assert client_for(grace).get(url).status_code == 200
    anonymous = client_for().get(url)
    assert anonymous.status_code == 401
    assert anonymous.data["code"] == "not_authenticated"


def test_section_toggle_change_is_audited_without_content(ada):
    _profile(ada)
    save_profile(ada, {"bio": "secret words", "show_links": False, "is_visible": False})
    meta = AuditLog.objects.filter(action="member.profile_updated", actor=ada).latest("created_at").meta
    # Decision 549: retired visibility metadata is gone; content-free audit remains exact.
    assert meta == {"fields": ["bio", "show_links"], "sections_changed": ["show_links"],
                    "attended_events_shown": True, "attended_events_changed": False,
                    "certifications_shown": True, "projects_before": 0, "projects_after": 0}
    assert "secret words" not in str(meta)


def test_status_note_cap_and_preset(ada):
    response = client_for(ada).put("/api/v1/member/profile", {"status": "student", "status_note": "x" * 121}, format="json")
    assert response.status_code == 400
    assert response.data["status_note"][0].code == "max_length"
    ok = client_for(ada).put("/api/v1/member/profile", {"status": "student", "status_note": "Finals"}, format="json")
    assert ok.status_code == 200 and ok.data["status"] == {"preset": "student", "note": "Finals"}
