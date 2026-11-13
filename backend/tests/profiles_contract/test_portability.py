from datetime import date
import pytest
from django.db import transaction
from django.utils import timezone
from apps.accounts.models import User
from apps.makerspaces.models import MemberProfile, MakerspaceMembership
from apps.makerspaces.models_profiles import ProfileTimelineEntry, PublicHandle
from apps.makerspaces.public_profile_handles import claim_handle, release_handle
from apps.tenant_migration.catalog_profiles import prepare_import_handle
from apps.tenant_migration.target_projection import TARGET_FIELD_PROJECTION
from apps.tenant_migration.tenant_dump_user_rows import apply_user_closure

pytestmark = pytest.mark.django_db


def test_export_registration_tenant_subject_json_and_user_decisions(published):
    from apps.data_export.models import EXPORTED_MODEL_FIELDS, OMITTED_MODELS
    from apps.data_export.datasets import DATASET_SPECS
    from apps.data_export.subject_selectors import subject_query
    from apps.data_export.references import RELATIONAL_USER_FIELDS, JSON_FIELDS
    from apps.data_export.guards import validate_model_and_field_coverage, validate_user_edges, validate_semantic_references
    from apps.tenant_migration.projection_guards import validate_unique_constraint_risks
    legacy = MemberProfile.objects.get_or_create(membership=published.membership)[0]
    entry = ProfileTimelineEntry.objects.create(profile=legacy, title="Authored", kind="education", start=date(2025, 1, 1))
    # Decision 305: the global profile and its children are account-level: omitted, never a tenant dataset.
    for label in ("makerspaces.AccountProfile", "makerspaces.AccountProject",
                  "makerspaces.AccountTimelineEntry", "makerspaces.ProfileAchievement"):
        assert label in OMITTED_MODELS and label not in DATASET_SPECS
    assert {"makerspaces.PublicHandle", "makerspaces.ProfileTimelineEntry"} <= EXPORTED_MODEL_FIELDS.keys()
    assert "makerspaces.PublicHandleRedirect" in OMITTED_MODELS
    assert ("makerspaces.PublicHandle", "user") in RELATIONAL_USER_FIELDS
    assert ("makerspaces.MemberProfile", "skills") in JSON_FIELDS
    assert DATASET_SPECS["makerspaces.PublicHandle"][1].any_paths == (
        "profile__membership__makerspace", "makerspace")  # a space's own handle rows reach it by `makerspace`
    assert subject_query(ProfileTimelineEntry, published.membership.user,
                         published.membership.makerspace_id).get().pk == entry.pk
    validate_model_and_field_coverage()
    validate_user_edges()
    validate_semantic_references()
    validate_unique_constraint_risks()


def test_import_publication_is_reset_but_authored_content_is_not():
    for name in ("public_visible", "show_activity_graph", "show_events", "show_speaking", "show_projects",
                 "show_machine_activity", "show_bookings", "show_loans"):
        assert TARGET_FIELD_PROJECTION[("makerspaces.MemberProfile", name)].value is False
    assert TARGET_FIELD_PROJECTION[("makerspaces.MemberProfile", "public_consented_at")].value is None
    assert TARGET_FIELD_PROJECTION[("makerspaces.MemberProject", "public_visible")].value is False
    assert ("makerspaces.MemberProfile", "bio") not in TARGET_FIELD_PROJECTION


def test_import_keeps_only_free_handle_and_never_overwrites_target_claim(membership):
    profile = MemberProfile.objects.create(membership=membership)
    row = {"user_id": membership.user_id, "profile_id": profile.pk, "handle": "imported.maker"}
    # A post-0.12 account owns a handle with NO legacy profile: that is a valid claim (decision 305) ...
    with transaction.atomic():
        assert prepare_import_handle({"user_id": membership.user_id, "profile_id": None, "handle": "account.level"})
    # ... but a row naming someone else's legacy profile is still refused.
    stranger = User.objects.create_user(username="import-stranger")
    stranger_membership = MakerspaceMembership.objects.create(
        user=stranger, makerspace=membership.makerspace,
        assigned_role=membership.makerspace.roles.get(slug="member"), role="custom")
    foreign = MemberProfile.objects.create(membership=stranger_membership)
    with transaction.atomic():
        assert not prepare_import_handle({"user_id": membership.user_id, "profile_id": foreign.pk, "handle": "mismatch.maker"})
    with transaction.atomic():
        assert prepare_import_handle(row)
        pending = {}
        assert prepare_import_handle(row, pending)
        assert not prepare_import_handle({**row, "handle": "another.free"}, pending)
    claim_handle(membership.user, "target.maker")
    other_user = User.objects.create_user(username="import-other")
    other = MakerspaceMembership.objects.create(user=other_user, makerspace=membership.makerspace, assigned_role=membership.makerspace.roles.get(slug="member"), role="custom")
    other_profile = MemberProfile.objects.create(membership=other)
    with transaction.atomic():
        assert not prepare_import_handle(row)
    row.update(user_id=other_user.pk, profile_id=other_profile.pk, handle="TARGET.MAKER")
    with transaction.atomic():
        assert not prepare_import_handle(row)
    assert PublicHandle.objects.get(user=membership.user).handle == "target.maker"
    release_handle(membership.user)
    with transaction.atomic():
        assert not prepare_import_handle(row)
    row["handle"] = "free.maker"
    with transaction.atomic():
        assert prepare_import_handle(row)


def test_stub_profile_drops_handle_and_timeline_together():
    class Closure:
        stubbed_user_ids = {5}
    rows = {
        "makerspaces.MakerspaceMembership": ({"id": 1, "user_id": 5},),
        "makerspaces.MemberProfile": ({"id": 2, "membership_id": 1},),
        "makerspaces.PublicHandle": ({"id": 3, "profile_id": 2},),
        "makerspaces.ProfileTimelineEntry": ({"id": 4, "profile_id": 2},),
    }
    projected = apply_user_closure(rows, Closure())
    assert projected["makerspaces.PublicHandle"] == ()
    assert projected["makerspaces.ProfileTimelineEntry"] == ()


def test_colliding_handle_mapping_is_removed_for_import_verification():
    from apps.tenant_migration.pk_maps import TransactionPkMap
    from apps.tenant_migration.insertion_errors import PrimaryKeyMapUnavailable
    with transaction.atomic():
        mapping = TransactionPkMap()
        mapping.reserve(PublicHandle, [991])
        assert mapping.count(PublicHandle) == 1
        mapping.discard_unmaterialized(PublicHandle, 991)
        assert mapping.count(PublicHandle) == 0
        with pytest.raises(PrimaryKeyMapUnavailable):
            mapping.lookup(PublicHandle, 991)


def test_membership_module_purge_cascades_legacy_timeline_but_keeps_the_accounts_handle(published):
    legacy = MemberProfile.objects.get_or_create(membership=published.membership)[0]
    PublicHandle.objects.filter(user=published.user).update(profile=legacy)
    ProfileTimelineEntry.objects.create(profile=legacy, title="Authored", kind="experience", start=date(2025, 1, 1))
    legacy.delete()
    assert not ProfileTimelineEntry.objects.exists()
    # Decision 305: the handle belongs to the account, so purging a legacy row only clears its pointer.
    assert PublicHandle.objects.get(user=published.user).profile_id is None


def test_portable_source_carries_authored_content_and_handle_but_resets_consent(published):
    import uuid
    from apps.makerspaces.models import MemberProject
    from apps.tenant_migration.tenant_dump_source_projection import project_makerspace_source
    # `save_profile` already made the legacy per-membership row (one per membership), so update it.
    legacy, _ = MemberProfile.objects.update_or_create(
        membership=published.membership,
        defaults=dict(domains=["Robotics"], show_projects=True, public_visible=True, public_consented_at=timezone.now()))
    MemberProject.objects.create(profile=legacy, title="Robot", subtitle="First build", tags=["robotics"],
                                 public_visible=True)
    PublicHandle.objects.filter(user=published.user).update(profile=legacy)
    ProfileTimelineEntry.objects.create(profile=legacy, title="Authored", kind="education", start=date(2025, 1, 1))
    projection = project_makerspace_source(published.membership.makerspace_id, capture_id=uuid.uuid4())
    from apps.tenant_migration.tenant_dump_raw import sanitize_record
    raw = projection.rows["makerspaces.MemberProfile"][0]
    assert raw["domains"] == ["Robotics"]
    # The source projection is raw; disclosure resets apply when the dump sanitizes the row.
    row = sanitize_record(MemberProfile, raw).values
    assert row["domains"] == ["Robotics"]
    assert row["public_visible"] is False and row["public_consented_at"] is None
    assert row["show_projects"] is False
    assert projection.rows["makerspaces.PublicHandle"][0]["handle"] == "public.maker"
    assert projection.rows["makerspaces.ProfileTimelineEntry"][0]["title"] == "Authored"
    # The global profile never travels in a tenant dump (decision 305).
    assert not any(label.startswith("makerspaces.Account") for label in projection.rows)
