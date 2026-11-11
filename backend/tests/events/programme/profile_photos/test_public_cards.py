from uuid import uuid4
import pytest
from django.utils import timezone

from apps.events.profile_photos import policy
from apps.events.profile_photos.models import EventMemberPresentation
from apps.events.profile_photos.projection import project_public
from apps.events.profile_photos.selection_workflow import select, source_revision
from apps.makerspaces.models_profiles import MemberProfile, PublicHandle
from tests.events.programme.profile_photos.test_selection import setup

pytestmark = pytest.mark.django_db


def test_card_uses_only_selected_public_profile_and_handle_move_never_substitutes_another_membership(monkeypatch, settings):
    settings.PUBLIC_APP_BASE_URL = "https://spaceworks.test"
    event, member, profile = setup()
    profile.public_visible, profile.public_consented_at = True, timezone.now()
    profile.save(update_fields=("public_visible", "public_consented_at", "updated_at"))
    handle = PublicHandle.objects.create(user=member, profile=profile, handle="selected-maker", changed_at=timezone.now())
    monkeypatch.setattr(policy, "_public_surfaces", {"team": lambda **kwargs: True})
    result = select(event.pk, actor=member, operation_id=uuid4(), expected_version=0,
        profile_id=profile.pk, membership_id=profile.membership_id, source_revision=source_revision(profile),
        public_card_consent=True, public_card_scopes=["team"])
    payload = project_public(event_id=event.pk, member_id=member.pk, scope="team")
    assert set(payload) == {"name", "skills", "role", "profile_url", "photo_url"}
    assert payload["profile_url"] == "https://spaceworks.test/selected-maker"
    assert "member-cards" in payload["photo_url"] and profile.avatar_key not in str(payload)
    assert project_public(event_id=event.pk, member_id=member.pk, scope="judge") is None
    other = MemberProfile.objects.create(membership=member.makerspace_memberships.get(makerspace=event.makerspace))
    handle.profile = other; handle.save(update_fields=("profile",))
    assert project_public(event_id=event.pk, member_id=member.pk, scope="team") is None


def test_private_print_consent_does_not_publish_and_public_withdrawal_takes_effect_immediately(monkeypatch):
    event, member, profile = setup()
    monkeypatch.setattr(policy, "_public_surfaces", {"team": lambda **kwargs: True})
    first = select(event.pk, actor=member, operation_id=uuid4(), expected_version=0,
        profile_id=profile.pk, membership_id=profile.membership_id, source_revision=source_revision(profile),
        print_photo_consent=True)
    assert project_public(event_id=event.pk, member_id=member.pk, scope="team") is None
    presentation = EventMemberPresentation.objects.get(pk=first["id"])
    assert policy.print_profile(presentation).pk == profile.pk
    select(event.pk, actor=member, operation_id=uuid4(), expected_version=first["version"],
        profile_id=None, membership_id=None, source_revision=None)
    presentation.refresh_from_db()
    assert policy.print_profile(presentation) is None
