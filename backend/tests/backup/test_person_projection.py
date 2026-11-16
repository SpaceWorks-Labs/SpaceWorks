"""Per-space archive formats and merged people across a per-space restore (U-D; local only).

tenant_slice_v2 carries both membership tracks; a v1 archive (no track column) converts
one version back; anything else is refused. Rows of a person merged since the restore
point follow ``merged_into`` to the survivor (#128 C-17), and a unique slot the survivor
already holds keeps the merged row on the shell, revoked.
"""

import json

import pytest
from django.db import connection, transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.backup.models import BackupArchive
from apps.backup.space_restore_apply import apply_space_restore
from apps.backup.space_restore_plan import SpaceArchive, SpaceRestoreError
from apps.backup.space_restore_preview import compute_preview
from apps.backup.space_restore_staging import require_restorable
from apps.hardware_requests.models import HardwareRequest
from apps.makerspaces.models import Makerspace, MakerspaceMembership
from tests.accounts.account_factories import grant_staff_role, make_membership
from tests.backup.space_restore_helpers import build_space_archive, make_user, seed_space
from tests.encryption.conftest import enabled_encryption

pytestmark = pytest.mark.django_db(transaction=True)


def _restore(space, archive):
    with transaction.atomic():
        return apply_space_restore(Makerspace.objects.select_for_update().get(pk=space.pk), archive)


def _rows(space):
    return set(MakerspaceMembership.all_tracks.filter(makerspace=space)
               .values_list("user_id", "track", "status", "assigned_role__slug"))


def _as_v1(archive, *, strip_track):
    manifest = {**archive.manifest, "payload_format": "tenant_slice_v1"}
    (archive.root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    if strip_track:
        path = archive.root / "tenant" / "makerspaces_makerspacemembership.json"
        rows = json.loads(path.read_text(encoding="utf-8"))
        for row in rows:
            row["fields"].pop("track")
        path.write_text(json.dumps(rows), encoding="utf-8")
    return SpaceArchive(archive.root)


def _merge(shell, survivor):
    """What U-C's merge engine leaves: the shell's rows revoked, the shell inert."""
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("SELECT set_config('app.account_unification_run_id', 'test-merge', true)")
        MakerspaceMembership.all_tracks.filter(user=shell).update(status="revoked", revoked_at=timezone.now())
        User._base_manager.filter(pk=shell.pk).update(
            account_kind="staff", merged_into=survivor, merged_at=timezone.now(), is_active=False)


def test_a_pre_unification_archive_converts_its_tracks_by_role(tmp_path):
    with enabled_encryption():
        member = make_user("v1-member")
        space, _request = seed_space("v1-space", member)
        staff = make_user("v1-staff")
        grant_staff_role(staff, space, role_slug="inventory_manager")
        before = _rows(space)
        archive = _as_v1(build_space_archive(space, tmp_path / "archive"), strip_track=True)
        assert {row["fields"]["track"] for row in archive.rows("makerspaces.MakerspaceMembership")} == {
            "community", "staff"}
        _restore(space, archive)
        assert _rows(space) == before


@pytest.mark.parametrize(("payload_format", "accepted"), [
    ("tenant_slice_v2", True), ("tenant_slice_v1", True), ("tenant_slice_v0", False), ("", False)])
def test_only_the_current_and_previous_formats_are_restorable(payload_format, accepted):
    space = Makerspace.objects.create(name="Formats", slug="formats")
    row = BackupArchive(scope="makerspace", makerspace=space, status="available", format=payload_format,
                        manifest={"server_restorable": True})
    if accepted:
        require_restorable(row, space)
    else:
        with pytest.raises(SpaceRestoreError) as refused:
            require_restorable(row, space)
        assert refused.value.code == "archive_not_restorable"


def test_rows_of_a_person_merged_since_follow_the_survivor(tmp_path):
    with enabled_encryption():
        member = make_user("merge-member")
        space, _request = seed_space("merge-space", member)
        shell, survivor = make_user("merge-shell"), make_user("merge-survivor")
        shell_community = make_membership(shell, space)
        make_membership(survivor, space)
        shell_staff = grant_staff_role(shell, space, role_slug="booking_manager")
        loan = HardwareRequest.objects.create(makerspace=space, requester=shell, requester_username=shell.username,
                                              requester_name="Merged person")
        archive = build_space_archive(space, tmp_path / "archive")
        _merge(shell, survivor)

        preview = compute_preview(space, archive)
        assert preview["accounts"]["merged_since"] == 1
        assert preview["accounts"]["merged_followed"] == [{"account": str(shell.pk), "survivor": str(survivor.pk)}]
        report = _restore(space, archive)

        assert HardwareRequest.objects.get(pk=loan.pk).requester_id == survivor.pk
        moved = MakerspaceMembership.all_tracks.get(pk=shell_staff.pk)
        assert (moved.user_id, moved.status) == (survivor.pk, "active")
        kept = MakerspaceMembership.all_tracks.get(pk=shell_community.pk)
        assert (kept.user_id, kept.status) == (shell.pk, "revoked")
        assert MakerspaceMembership.objects.get(makerspace=space, user=survivor).status == "active"
        assert report["merges_followed"] >= 2 and report["merged_rows_kept_on_shells"] == 1
        shell.refresh_from_db()
        assert shell.is_active is False and shell.merged_into_id == survivor.pk


def test_a_pre_unification_platform_backup_needs_the_operator_ack(monkeypatch):
    from apps.backup import space_extract

    seen = {}

    def migrate(*_args, **_kwargs):
        from django.conf import settings
        seen["ack"] = settings.ACCOUNT_UNIFICATION_ACK
        if settings.ACCOUNT_UNIFICATION_ACK != "abc123":
            raise RuntimeError("Account unification would convert 2 staff account(s). Run ...")

    monkeypatch.setattr(space_extract, "call_command", migrate)
    monkeypatch.setattr("apps.accounts.unification_plan.build_plan",
                        lambda _connection: {"staff_accounts": [1, 2], "plan_sha256": "abc123"})
    with pytest.raises(SpaceRestoreError) as refused:
        space_extract._migrate_scratch("default", None)
    assert refused.value.code == "unification_ack_required" and "abc123" in str(refused.value)
    space_extract._migrate_scratch("default", "abc123")
    assert seen["ack"] == "abc123"
