"""Account-level classification (export/dump), the directory projection and the account merge."""
import pytest

from apps.accounts import merge_registry
from apps.data_export.classification import OMITTED_MODELS
from apps.makerspaces.account_profile import account_profile_for, save_profile
from apps.makerspaces.account_profile_account_merge import merge_profiles
from apps.makerspaces.models import AccountProfile, AccountProject, AccountTimelineEntry, ProfileAchievement
from apps.makerspaces.profile_directory import directory
from apps.tenant_migration.tenant_dump_model_catalog import PROJECTED_MODEL_LABELS

from .conftest import make_person

pytestmark = pytest.mark.django_db
LABELS = ("makerspaces.AccountProfile", "makerspaces.AccountProject", "makerspaces.AccountTimelineEntry",
          "makerspaces.ProfileAchievement")


def test_account_models_are_omitted_from_exports_and_never_projected_into_a_dump():
    for label in LABELS:
        assert label in OMITTED_MODELS
        assert label not in PROJECTED_MODEL_LABELS


def test_user_fk_has_a_merge_disposition():
    assert merge_registry.disposition_for("makerspaces.AccountProfile", "user") == merge_registry.UNIQUE_RESOLVE


def test_directory_lists_only_space_members_with_name_headline_avatar(ada, grace, space_a, stranger):
    account_profile_for(ada)
    save_profile(ada, {"headline": "Engines"})
    save_profile(grace, {"is_visible": False})
    result = directory(space_a)
    assert [m["display_name"] for m in result["members"]] == ["Ada"]
    assert set(result["members"][0]) == {"membership_id", "display_name", "headline", "avatar_url"}
    assert result["hidden_count"] == 1


def test_account_merge_combines_content_into_survivor(ada):
    other = make_person("ada-second")
    keep = account_profile_for(ada)
    drop = account_profile_for(other)
    AccountProfile.objects.filter(pk=keep.pk).update(headline="Keep", skills=[{"name": "CAD", "level": 1}])
    AccountProfile.objects.filter(pk=drop.pk).update(
        headline="Drop", bio="from source", skills=[{"name": "cad", "level": 2}, {"name": "Weld", "level": 1}])
    AccountProject.objects.create(profile=drop, title="Lathe")
    AccountTimelineEntry.objects.create(profile=drop, kind="experience", title="Eng", start="2020-01-01")
    ProfileAchievement.objects.create(profile=drop, title="Prize")
    assert merge_profiles(other.pk, ada.pk) is True
    keep.refresh_from_db()
    assert keep.headline == "Keep" and keep.bio == "from source"
    assert sorted(s["name"].lower() for s in keep.skills) == ["cad", "weld"]
    assert keep.projects.count() == keep.timeline.count() == keep.achievements.count() == 1
    assert not AccountProfile.objects.filter(user=other).exists()


def test_account_merge_with_one_profile_is_a_no_op_for_the_combiner(ada):
    other = make_person("ada-third")
    account_profile_for(other)
    assert merge_profiles(other.pk, ada.pk) is False  # registry moves the lone row instead
