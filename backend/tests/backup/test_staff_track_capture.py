"""Both membership tracks survive capture, per-space restore, tenant dump and export.

``MakerspaceMembership.objects`` is community-only, so the generic capture loops used to
drop every staff-track row: a per-space archive lost the space's staff and restoring it
deleted them (local only, never committed).
"""

import csv
import io
import json
import zipfile
from datetime import timedelta

import pytest
from django.db import transaction
from django.utils import timezone

from apps.backup.space_restore_apply import apply_space_restore
from apps.backup.space_restore_plan import SpaceRestoreError
from apps.backup.space_restore_preview import compute_preview
from apps.data_export.models import DataExportJob
from apps.data_export.runner import build_archive
from apps.makerspaces.models import Makerspace, MakerspaceMembership, MembershipAdditionalRole
from apps.tenant_migration.tenant_dump_source_projection import project_makerspace_source
from tests.accounts.account_factories import grant_staff_role, make_membership
from tests.backup.space_restore_helpers import build_space_archive, make_user, seed_space
from tests.encryption.conftest import enabled_encryption

pytestmark = pytest.mark.django_db(transaction=True)

STAFF = MakerspaceMembership.Track.STAFF
COMMUNITY = MakerspaceMembership.Track.COMMUNITY


def _two_track_space(slug):
    member = make_user(f"{slug}-member")
    space, _request = seed_space(slug, member)
    person = make_user(f"{slug}-person")
    make_membership(person, space)
    staff_row = grant_staff_role(person, space, role_slug="inventory_manager")
    MembershipAdditionalRole.objects.create(membership=staff_row, role=space.roles.get(slug="event_manager"))
    manager = make_user(f"{slug}-manager")
    grant_staff_role(manager, space, role_slug="space_manager")
    return space, person, staff_row


def _tracks(space):
    return set(MakerspaceMembership.all_tracks.filter(makerspace=space)
               .values_list("user__username", "track", "status", "assigned_role__slug"))


def _restore(space, archive):
    with transaction.atomic():
        return apply_space_restore(Makerspace.objects.select_for_update().get(pk=space.pk), archive)


def test_per_space_archive_and_restore_keep_both_tracks(tmp_path):
    with enabled_encryption():
        space, person, staff_row = _two_track_space("tracks-roundtrip")
        before = _tracks(space)
        archive = build_space_archive(space, tmp_path / "archive")
        archived = {(row["fields"]["user"], row["fields"]["track"])
                    for row in archive.rows("makerspaces.MakerspaceMembership")}
        assert (person.pk, STAFF) in archived and (person.pk, COMMUNITY) in archived
        assert archive.rows("makerspaces.MembershipAdditionalRole")

        # Drift after the restore point: the staff role is revoked.
        MakerspaceMembership.staff_tracks.filter(pk=staff_row.pk).update(status="revoked")
        _restore(space, archive)

        assert _tracks(space) == before
        assert MembershipAdditionalRole.objects.filter(membership_id=staff_row.pk).exists()


def test_staff_granted_after_the_restore_point_blocks_the_restore(tmp_path):
    with enabled_encryption():
        space, _person, _staff_row = _two_track_space("tracks-later")
        archive = build_space_archive(space, tmp_path / "archive")
        later = make_user("tracks-later-staff")
        grant_staff_role(later, space, role_slug="machine_manager")

        preview = compute_preview(space, archive)
        assert any(item["reason"] == "staff_after_restore_point" and item["pk"] == str(later.pk)
                   for item in preview["blocking"])
        assert preview["blocked"] is True
        with pytest.raises(SpaceRestoreError) as refused:
            _restore(space, archive)
        assert refused.value.code == "staff_after_restore_point"
        assert MakerspaceMembership.staff_tracks.filter(makerspace=space, user=later, status="active").exists()


def test_an_archive_missing_staff_rows_blocks_instead_of_deleting_them(tmp_path):
    with enabled_encryption():
        space, _person, _staff_row = _two_track_space("tracks-old-archive")
        archive = build_space_archive(space, tmp_path / "archive")
        path = archive.root / "tenant" / "makerspaces_makerspacemembership.json"
        rows = json.loads(path.read_text(encoding="utf-8"))
        path.write_text(json.dumps([row for row in rows if row["fields"]["track"] != STAFF]), encoding="utf-8")
        archive._rows.clear()
        with pytest.raises(SpaceRestoreError) as refused:
            _restore(space, archive)
        assert refused.value.code == "staff_after_restore_point"
        assert MakerspaceMembership.staff_tracks.filter(makerspace=space).count() == 2


def test_tenant_dump_source_projection_carries_both_tracks():
    with enabled_encryption():
        space, person, staff_row = _two_track_space("tracks-dump")
        projection = project_makerspace_source(space.pk)
        rows = {(row["user_id"], row["track"]) for row in projection.rows["makerspaces.MakerspaceMembership"]}
        assert {(person.pk, STAFF), (person.pk, COMMUNITY)} <= rows
        assert {row["membership_id"] for row in projection.rows["makerspaces.MembershipAdditionalRole"]} == {staff_row.pk}


def test_space_export_roster_includes_staff_rows():
    with enabled_encryption():
        space, person, _staff_row = _two_track_space("tracks-export")
        job = DataExportJob.objects.create(
            makerspace=space, requested_by=person, fidelity="REDACTED", status=DataExportJob.Status.RUNNING,
            object_key=f"data-exports/{space.pk}/tracks.zip", deadline_at=timezone.now() + timedelta(minutes=5),
            expires_at=timezone.now() + timedelta(days=1))
        path, _manifest, tempdir = build_archive(job, page_size=50)
        try:
            with zipfile.ZipFile(path) as bundle:
                roster = list(csv.DictReader(io.StringIO(bundle.read("members/roster.csv").decode("utf-8"))))
                users = bundle.read("global/users.csv").decode("utf-8")
        finally:
            tempdir.cleanup()
    user_column = "user" if "user" in roster[0] else "user_id"
    tracks = {(row[user_column], row["track"]) for row in roster}
    assert {(str(person.pk), STAFF), (str(person.pk), COMMUNITY)} <= tracks
    assert sum(1 for row in roster if row["track"] == STAFF) == 2
    assert person.username in users
