"""SECURITY-REVIEW H2 / decision 335c: the legacy merge never widens what a member published."""
from datetime import date

import pytest
from django.utils import timezone

from apps.makerspaces import account_profile_merge as merge
from apps.makerspaces.account_profile import save_profile
from apps.makerspaces.models import MemberProfile, MemberProject, ProfileTimelineEntry

from .test_migration_merge import legacy, real_models

pytestmark = pytest.mark.django_db


def test_content_of_a_hidden_profile_never_reaches_the_visible_merged_profile(ada, space_a, space_b):
    shown = legacy(ada, space_a, is_visible=True, headline="Shown", bio="public bio", interests=["Wood"],
                   links=[{"kind": "web", "url": "https://shown.test"}])
    hidden = legacy(ada, space_b, is_visible=False, bio="private bio", interests=["Secret"],
                    links=[{"kind": "web", "url": "https://private.test"}])
    MemberProfile.objects.filter(pk=hidden.pk).update(updated_at=timezone.now())  # the hidden one is newest
    ProfileTimelineEntry.objects.create(profile=hidden, kind="experience", title="Hidden job", start=date(2020, 1, 1))
    MemberProject.objects.create(profile=hidden, title="Hidden project", public_visible=True)
    MemberProject.objects.create(profile=shown, title="Shown project", public_visible=True)
    account = merge.merge_user(real_models(), ada.pk)
    assert account.is_visible is True
    assert account.bio == "public bio" and account.headline == "Shown"
    assert account.interests == ["Wood"] and [row["url"] for row in account.links] == ["https://shown.test"]
    assert not account.timeline.exists()
    assert list(account.projects.values_list("title", flat=True)) == ["Shown project"]


def test_legacy_publication_opt_outs_stay_off(ada, space_a, space_b):
    legacy(ada, space_a, is_visible=True)  # every legacy consent defaults False
    account = merge.merge_user(real_models(), ada.pk)
    for name in ("show_events", "show_activity_graph", "show_projects", "show_certifications", "show_speaking",
                 "show_machine_activity", "show_bookings", "show_loans"):
        assert getattr(account, name) is False, name
    # Sections that never had a legacy switch keep the open default (decision 303a).
    assert account.show_about is True and account.show_experience is True


def test_a_legacy_yes_from_a_contributing_row_carries_over(ada, space_a, space_b):
    legacy(ada, space_a, is_visible=True, show_attended_events=True, show_activity_graph=True, show_projects=True)
    legacy(ada, space_b, is_visible=False, show_speaking=True)  # not a contributing row: its yes is ignored
    account = merge.merge_user(real_models(), ada.pk)
    assert account.show_events and account.show_activity_graph and account.show_projects
    assert account.show_speaking is False


def test_open_web_needs_every_contributing_profile_to_have_consented(ada, space_a, space_b):
    stamp = timezone.now()
    legacy(ada, space_a, is_visible=True, public_visible=True, public_consented_at=stamp)
    legacy(ada, space_b, is_visible=True)
    account = merge.merge_user(real_models(), ada.pk)
    assert account.public_visible is False and account.public_consented_at is None
    assert account.public_reconfirm_pending is True and account.open_notice_pending is True


def test_open_web_stays_on_when_every_contributing_profile_consented(ada, space_a, space_b):
    stamp = timezone.now()
    legacy(ada, space_a, is_visible=True, public_visible=True, public_consented_at=stamp)
    legacy(ada, space_b, is_visible=True, public_visible=True, public_consented_at=stamp)
    account = merge.merge_user(real_models(), ada.pk)
    assert account.public_visible is True and account.public_consented_at == stamp
    assert account.public_reconfirm_pending is False


def test_any_explicit_open_web_choice_answers_the_reconfirmation(ada, space_a, space_b):
    stamp = timezone.now()
    legacy(ada, space_a, is_visible=True, public_visible=True, public_consented_at=stamp)
    legacy(ada, space_b, is_visible=True)
    account = merge.merge_user(real_models(), ada.pk)
    assert account.public_reconfirm_pending is True
    save_profile(ada, {"public_visible": False})  # "Keep it off the open web"
    account.refresh_from_db()
    assert account.public_reconfirm_pending is False and account.public_visible is False


def test_the_owner_payload_carries_the_reconfirmation_flag_and_others_never_see_it(ada, grace, space_a, space_b):
    from .conftest import client_for

    stamp = timezone.now()
    legacy(ada, space_a, is_visible=True, public_visible=True, public_consented_at=stamp)
    legacy(ada, space_b, is_visible=True)
    merge.merge_user(real_models(), ada.pk)
    own = client_for(ada).get("/api/v1/member/profile")
    assert own.status_code == 200 and own.data["public_reconfirm_pending"] is True
    other = client_for(grace).get(f"/api/v1/profiles/by-account/{ada.pk}/")
    assert other.status_code == 200 and "public_reconfirm_pending" not in other.data
