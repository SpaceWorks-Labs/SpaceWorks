from uuid import uuid4

import pytest
from django.db import connection, transaction

from apps.events.profile_photos.models import EventMemberPresentation
from apps.events.profile_photos.selection_workflow import select, source_revision
from apps.makerspaces.models_profiles import MemberProfile
from tests.events.programme.profile_photos.test_selection import setup

pytestmark = pytest.mark.django_db(transaction=True)


def selected():
    event, member, profile = setup()
    result = select(event.pk, actor=member, operation_id=uuid4(), expected_version=0,
        profile_id=profile.pk, membership_id=profile.membership_id, source_revision=source_revision(profile),
        print_photo_consent=True, public_card_consent=True, public_card_scopes=["team"])
    return profile, EventMemberPresentation.objects.get(pk=result["id"])


def assert_cleared(row):
    row.refresh_from_db()
    assert row.selected_profile_id is None and row.selected_membership_id is None
    assert not row.print_photo_consent and not row.public_card_consent and row.public_card_scopes == []
    assert not row.source_revision and row.consented_at is None and row.revoked_at is not None


@pytest.mark.parametrize("source", ["profile", "membership"])
def test_orm_source_deletion_clears_both_references_and_consents_together(source):
    profile, row = selected()
    old_version, old_consent = row.version, row.consent_revision
    (profile if source == "profile" else profile.membership).delete()
    assert_cleared(row)
    assert row.version == old_version + 1 and row.consent_revision == old_consent + 1


def test_rollback_of_source_deletion_restores_selection_and_consent():
    profile, row = selected()
    profile_id = profile.pk
    with pytest.raises(RuntimeError):
        with transaction.atomic():
            profile.delete()
            assert_cleared(row)
            raise RuntimeError("Rollback parent deletion")
    row.refresh_from_db()
    assert MemberProfile.objects.filter(pk=profile_id).exists()
    assert row.selected_profile_id == profile_id and row.print_photo_consent and row.public_card_consent


def test_sql_profile_delete_cannot_leave_a_half_selection():
    profile, row = selected()
    with transaction.atomic(), connection.cursor() as cursor:
        cursor.execute("DELETE FROM makerspaces_memberprofile WHERE id=%s", [profile.pk])
    assert_cleared(row)


def test_ordered_source_deletion_discovers_foreign_event_before_locks():
    from apps.events.profile_photos.deletion import delete_source
    profile, row = selected()
    delete_source("profile", profile.pk, actor=row.member)
    assert_cleared(row)


def test_erased_account_cannot_reselect_a_photo():
    from apps.accounts.saved_details.lifecycle import erase_account_vault
    from apps.encryption.account_write_fence import AccountKeyChanged
    profile, row = selected()
    member = row.member
    erase_account_vault(member.pk, actor=member)
    assert_cleared(row)
    with pytest.raises(AccountKeyChanged):
        select(row.event_id, actor=member, operation_id=uuid4(), expected_version=row.version,
            profile_id=profile.pk, membership_id=profile.membership_id, source_revision=source_revision(profile),
            print_photo_consent=True)
