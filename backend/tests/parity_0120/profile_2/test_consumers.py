"""Every remaining consumer of the profile reads the ACCOUNT profile (decisions 303-305).

A brand-new account has NO legacy per-membership content, yet must show correctly in: stored page
references (profile_is_public), public pages' team sections and handle resolution, event crew,
event profile photo cards, API-client target resolution and the presence display helper. Hidden or
unconsented profiles stay hidden in embedded readers; decision 549 makes the shared handle card always available.
"""
import pytest
from django.utils import timezone
from rest_framework.exceptions import NotFound

from apps.makerspaces.account_profile import account_profile_for, ensure_legacy_pointers
from apps.makerspaces.models import AccountProfile, MemberProfile, PublicHandle
from apps.makerspaces.public_profile_access import account_is_open_web, profile_is_public, resolve_public_profile
from tests.l21a_local.test_crew_and_lists import EventCrewMember, EventParticipationSettings, crew_workflow, world
from tests.l21a_local.test_crew_and_lists import make_member as crew_member


pytestmark = pytest.mark.django_db


def open_to_web(user):
    # Decision 549: seed stored legacy consent for embedded readers; the card needs none.
    profile = account_profile_for(user)
    AccountProfile.objects.filter(pk=profile.pk).update(public_visible=True, public_consented_at=timezone.now())


def pointer_for(user, space):
    ensure_legacy_pointers(user)
    return MemberProfile.objects.get(membership__user=user, membership__makerspace=space)


# --- the shared predicate behind stored references ------------------------------------------------


def test_new_account_with_no_legacy_content_is_public_through_its_reference_token(space_a, ada):
    account_profile_for(ada)
    pointer = pointer_for(ada, space_a)
    assert pointer.headline == "" and not pointer.public_visible  # the legacy row carries nothing
    assert profile_is_public(pointer) is False  # open web is still off by default
    open_to_web(ada)
    assert profile_is_public(pointer) is True


@pytest.mark.parametrize("hide", ["profile", "consent", "handle", "restricted", "revoked"])
def test_hidden_account_profile_stays_hidden_through_the_reference_token(space_a, ada, hide):
    account_profile_for(ada)
    open_to_web(ada)
    pointer = pointer_for(ada, space_a)
    assert profile_is_public(pointer) is True
    if hide == "profile":
        AccountProfile.objects.filter(user=ada).update(is_visible=False)  # 549: legacy fixture
    elif hide == "consent":
        AccountProfile.objects.filter(user=ada).update(public_visible=False)  # 549: legacy fixture
    elif hide == "handle":
        PublicHandle.objects.filter(user=ada).delete()
    elif hide == "restricted":
        ada.access_status = "restricted"
        ada.save(update_fields=["access_status"])
    else:
        pointer.membership.status = "revoked"
        pointer.membership.save(update_fields=["status"])
    pointer = pointer_for(ada, space_a)  # re-read: the cached pointer still holds the pre-change user row
    assert profile_is_public(pointer) is False
    assert account_is_open_web(ada) is (hide == "revoked")


def test_pointers_are_created_with_the_profile_and_mirror_the_avatar(space_a, ada):
    from apps.makerspaces.account_profile import mirror_avatar
    account_profile_for(ada)
    assert MemberProfile.objects.filter(membership__user=ada).count() == 2  # one per active membership
    mirror_avatar(ada, f"member/{space_a.pk}/new.png")
    assert set(MemberProfile.objects.filter(membership__user=ada).values_list("avatar_key", flat=True)) == {
        f"member/{space_a.pk}/new.png"}


# --- handle resolution (public pages, API clients) ---------------------------------------------------


def test_resolve_public_profile_uses_the_account_and_one_404(ada):
    account_profile_for(ada)
    handle = PublicHandle.objects.get(user=ada).handle
    with pytest.raises(NotFound):
        resolve_public_profile(handle)
    open_to_web(ada)
    claim, redirected = resolve_public_profile(handle)
    assert claim.user_id == ada.pk and redirected is False
    AccountProfile.objects.filter(user=ada).update(is_visible=False)  # 549: legacy fixture
    with pytest.raises(NotFound):
        resolve_public_profile(handle)


def test_public_page_handle_resolution_and_api_client_target_for_a_new_account(space_a, ada, settings):
    settings.PUBLIC_APP_BASE_URL = "http://testserver"
    from apps.makerspaces.public_page_access import resolve_handle
    from apps.makerspaces.profile_images import home_space
    account_profile_for(ada)
    handle = PublicHandle.objects.get(user=ada).handle
    # Decision 549: the shared handle resolver now admits an unconsented card.
    claim, result = resolve_handle(handle)
    assert result == {"kind": "member", "handle": handle, "canonical_url": f"http://testserver/@{handle}",
                      "redirected": False, "content_url": f"/api/v1/public/profiles/{handle}/"}
    assert home_space(claim.user) is not None  # API-client target resolution uses the home space


# --- public pages: team section ----------------------------------------------------------------------


def test_page_team_section_shows_a_new_account_with_its_account_avatar_and_hides_a_hidden_one(space_a, ada):
    from apps.makerspaces.public_page_projection import project_team
    from types import SimpleNamespace
    account_profile_for(ada)
    open_to_web(ada)
    AccountProfile.objects.filter(user=ada).update(avatar_key=f"member/{space_a.pk}/me.png")
    pointer = pointer_for(ada, space_a)
    revision = SimpleNamespace(member_references=SimpleNamespace(
        select_related=lambda *a: [SimpleNamespace(slot="s1", profile=pointer)]))
    entries = [{"id": "e1", "kind": "member", "role": "Host", "member_slot_id": "s1"}]
    shown = project_team(entries, revision, None)
    assert [row["display_name"] for row in shown] == [ada.display_name]
    assert shown[0]["handle"] == PublicHandle.objects.get(user=ada).handle
    assert shown[0]["avatar_url"] and "me.png" in shown[0]["avatar_url"]
    AccountProfile.objects.filter(user=ada).update(is_visible=False)  # 549: legacy fixture
    assert project_team(entries, revision, None) == []


# --- event crew -----------------------------------------------------------------------------------------


def test_public_crew_lists_a_new_account_and_drops_a_hidden_one():
    space, event, staff = world("crew-acct", "events.crew")
    member = crew_member(space, "crew-new")
    crew = crew_workflow.add(event, actor=staff, member=member, crew_role="Host")
    EventCrewMember.objects.filter(pk=crew.pk).update(show_publicly=True)
    EventParticipationSettings.objects.create(makerspace=space, event=event, crew_public_section=True)
    from apps.events.contributions import crew_reads
    account_profile_for(member)
    assert crew_reads.public_crew(event) == []  # open web is off
    open_to_web(member)
    rows = crew_reads.public_crew(event)
    assert [(r["handle"], r["crew_role"]) for r in rows] == [(PublicHandle.objects.get(user=member).handle, "Host")]
    AccountProfile.objects.filter(user=member).update(is_visible=False)  # 549: legacy fixture
    assert crew_reads.public_crew(event) == []


# --- event profile photo cards ------------------------------------------------------------------------------


def test_photo_options_offer_a_new_account_its_account_avatar_and_a_hidden_profile_is_not_eligible(space_a, ada):
    from apps.events.profile_photos import selection_workflow as photos
    account_profile_for(ada)
    open_to_web(ada)
    AccountProfile.objects.filter(user=ada).update(avatar_key=f"member/{space_a.pk}/me.png")
    from apps.makerspaces.account_profile import mirror_avatar
    mirror_avatar(ada, f"member/{space_a.pk}/me.png")
    pointer = pointer_for(ada, space_a)
    assert photos.profile_is_public(pointer) is True and pointer.avatar_key.endswith("me.png")
    AccountProfile.objects.filter(user=ada).update(is_visible=False)  # 549: legacy fixture
    assert photos.profile_is_public(pointer) is False


# --- presence display helper ------------------------------------------------------------------------------------


def test_presence_display_helper_follows_the_account_profile(space_a, ada):
    """`presence.display` gates the project title on `account_is_open_web`, the account predicate behind `profile_is_public`."""
    from apps.presence import display
    assert display.account_is_open_web is account_is_open_web
    assert account_is_open_web(ada) is False
    account_profile_for(ada)
    pointer = pointer_for(ada, space_a)
    assert profile_is_public(pointer) is False
    open_to_web(ada)
    assert profile_is_public(pointer) is True
