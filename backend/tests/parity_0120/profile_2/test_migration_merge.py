"""Legacy per-membership profiles merged into one account profile (304d, 303d)."""
from datetime import date, timedelta
from types import SimpleNamespace

import pytest
from django.apps import apps as django_apps
from django.utils import timezone

from apps.audit import services as audit
from apps.makerspaces import account_profile_merge as merge
from apps.makerspaces.models import (
    AccountProfile, MakerspaceMembership, MemberProfile, MemberProject, ProfileTimelineEntry, PublicHandle,
)

pytestmark = pytest.mark.django_db
NAMES = ("AccountProfile", "AccountProject", "AccountTimelineEntry", "MemberProfile", "MemberProject",
         "ProfileTimelineEntry")


def real_models():
    models = {n: django_apps.get_model("makerspaces", n) for n in NAMES}
    models["AuditLog"] = django_apps.get_model("audit", "AuditLog")
    return SimpleNamespace(**models)


def legacy(user, space, **fields):
    membership = MakerspaceMembership.all_tracks.get(user=user, makerspace=space)
    return MemberProfile.objects.create(membership=membership, **fields)


def test_merges_most_recent_and_unions_the_rest(ada, space_a, space_b):
    older = legacy(ada, space_a, headline="Old", bio="old bio", skills=[{"name": "Welding", "level": 1}],
                   links=[{"kind": "web", "url": "https://a.test"}], interests=["Metal"])
    newer = legacy(ada, space_b, headline="New", skills=[{"name": "welding", "level": 3}, {"name": "CAD", "level": 2}],
                   links=[{"kind": "web", "url": "https://A.test"}, {"kind": "x", "url": "https://b.test"}],
                   interests=["metal", "Wood"])
    MemberProfile.objects.filter(pk=older.pk).update(updated_at=timezone.now() - timedelta(days=5))
    for profile in (older, newer):
        ProfileTimelineEntry.objects.create(profile=profile, kind="experience", title="Engineer",
                                            organization="Acme", start=date(2020, 1, 1))
    ProfileTimelineEntry.objects.create(profile=older, kind="education", title="BSc", start=date(2016, 1, 1))
    MemberProject.objects.create(profile=older, title="Lathe", image_key="member/1/x.png")
    MemberProject.objects.create(profile=newer, title="lathe")
    account = merge.merge_user(real_models(), ada.pk)
    assert account.headline == "New" and account.bio == "old bio"
    assert {s["name"].lower(): s["level"] for s in account.skills} == {"welding": 3, "cad": 2}
    assert len(account.links) == 2 and len(account.interests) == 2
    assert account.timeline.count() == 2 and account.projects.count() == 1
    assert MemberProfile.objects.count() == 2  # legacy rows untouched


def test_is_idempotent_and_skips_users_without_legacy_rows(ada, grace, space_a):
    legacy(ada, space_a, headline="H")
    assert merge.merge_user(real_models(), ada.pk) is not None
    assert merge.merge_user(real_models(), ada.pk) is None
    assert merge.merge_user(real_models(), grace.pk) is None
    assert AccountProfile.objects.count() == 1


def test_handle_keeps_resolving_after_merge(ada, space_a):
    profile = legacy(ada, space_a)
    PublicHandle.objects.create(user=ada, profile=profile, handle="ada-l", changed_at=timezone.now())
    merge.merge_user(real_models(), ada.pk)
    assert PublicHandle.objects.get(user=ada).handle == "ada-l"  # resolves through the user to the account profile


def test_303d_no_recorded_change_means_open_and_notice(ada, space_a):
    legacy(ada, space_a, is_visible=False)  # default-off at the time, never changed by the member
    account = merge.merge_user(real_models(), ada.pk)
    assert account.is_visible is True and account.open_notice_pending is True
    assert account.merged_from_legacy is True


def test_303d_explicit_hide_stays_hidden(ada, grace, space_a):
    legacy(ada, space_a, is_visible=False)
    legacy(grace, space_a, is_visible=True)
    audit.record(ada, "member.profile_updated", meta={"visibility_changed": True, "is_visible": False})
    audit.record(grace, "member.profile_updated", meta={"visibility_changed": False, "is_visible": True})
    hidden = merge.merge_user(real_models(), ada.pk)
    opened = merge.merge_user(real_models(), grace.pk)
    assert hidden.is_visible is False and hidden.open_notice_pending is False
    assert opened.is_visible is True


def test_explicit_hide_then_show_is_visible(ada, space_a):
    legacy(ada, space_a)
    audit.record(ada, "member.profile_updated", meta={"visibility_changed": True, "is_visible": False})
    audit.record(ada, "member.profile_updated", meta={"visibility_changed": True, "is_visible": True})
    assert merge.merge_user(real_models(), ada.pk).is_visible is True


def test_open_web_consent_is_preserved_never_invented(ada, grace, space_a):
    stamp = timezone.now()
    legacy(ada, space_a, public_visible=True, public_consented_at=stamp)
    legacy(grace, space_a)
    assert merge.merge_user(real_models(), ada.pk).public_visible is True
    assert merge.merge_user(real_models(), grace.pk).public_visible is False
