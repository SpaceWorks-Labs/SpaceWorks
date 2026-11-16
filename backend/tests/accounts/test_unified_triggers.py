"""Database guards for one account per person (accounts 0049, makerspaces 0114)."""

import uuid

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, InternalError, transaction
from django.utils import timezone

from apps.accounts.models import AccountMergeRecord, User
from apps.makerspaces.models import MakerspaceMembership, MembershipAdditionalRole

from .ua1_helpers import community, flush, guc, merged_shell, person, platform, space, sql, staff_row

pytestmark = pytest.mark.django_db
REFUSED = (IntegrityError, InternalError)


def _insert_like(template, **values):
    fields = [field for field in User._meta.concrete_fields if not field.primary_key]
    payload = {field.column: getattr(template, field.attname) for field in fields}
    payload.update(values, username=f"raw-{uuid.uuid4().hex[:8]}", email="")
    columns = ", ".join(f'"{column}"' for column in payload)
    sql(f"INSERT INTO accounts_user ({columns}) VALUES ({', '.join(['%s'] * len(payload))})",
        list(payload.values()))


def test_a_shell_is_inserted_only_by_an_exact_tenant_import():
    template = person("template")
    with pytest.raises(REFUSED), transaction.atomic():
        _insert_like(template, account_kind="staff", is_active=False, retired_at=timezone.now())
    guc("app.account_shell_import_job_id", uuid.uuid4())  # no such running job
    with pytest.raises(REFUSED), transaction.atomic():
        _insert_like(template, account_kind="staff", is_active=False, retired_at=timezone.now())


def test_person_becomes_a_merged_shell_only_in_a_unification_run():
    source, survivor = person("source"), person("survivor")
    with pytest.raises(REFUSED), transaction.atomic():
        User.objects.filter(pk=source.pk).update(
            account_kind="staff", merged_into=survivor, merged_at=timezone.now(), is_active=False)
    shell = merged_shell(source, survivor)
    assert shell.account_kind == "staff" and shell.merged_into_id == survivor.pk


def test_merge_alias_and_kind_are_frozen_outside_their_owners():
    shell = merged_shell(person("a"), person("b"))
    other = person("c")
    with pytest.raises(REFUSED), transaction.atomic():
        User.objects.filter(pk=shell.pk).update(merged_into=other)
    with pytest.raises(REFUSED), transaction.atomic():
        User.objects.filter(pk=shell.pk).update(account_kind="member", merged_into=None, merged_at=None)
    with pytest.raises(REFUSED), transaction.atomic():
        User.objects.filter(pk=shell.pk).delete()
    platform_user = platform()
    with pytest.raises(REFUSED), transaction.atomic():
        User.objects.filter(pk=platform_user.pk).update(account_kind="member")


def test_model_twin_refuses_kind_change_before_the_database():
    user = person("twin")
    user.account_kind = "staff"
    with pytest.raises(ValidationError):
        user.save()


def test_track_rules_hold_at_commit():
    makerspace, user = space("rules"), person("rules")
    community(user, makerspace)
    staff_row(user, makerspace, "inventory_manager", extra=("event_manager",))
    flush()  # one person, both tracks, combinable staff roles: valid
    with pytest.raises(REFUSED), transaction.atomic():
        MakerspaceMembership.objects.create(
            user=person("bad-community"), makerspace=makerspace, role="custom",
            assigned_role=makerspace.roles.get(slug="inventory_manager"))
        flush()
    with pytest.raises(REFUSED), transaction.atomic():
        staff_row(person("bad-staff"), makerspace, "member")
        flush()
    with pytest.raises(REFUSED), transaction.atomic():
        staff_row(person("sm-plus"), makerspace, "space_manager", extra=("event_manager",))
        flush()
    with pytest.raises(REFUSED), transaction.atomic():
        community(platform(), makerspace)
        flush()


def test_one_row_per_track_and_track_is_immutable():
    makerspace, user = space("unique"), person("unique")
    row = staff_row(user, makerspace, "event_manager")
    with pytest.raises(IntegrityError), transaction.atomic():
        staff_row(user, makerspace, "booking_manager")
    with pytest.raises(REFUSED), transaction.atomic():
        MakerspaceMembership.staff_tracks.filter(pk=row.pk).update(track="community")


def test_staff_rows_are_revoked_not_deleted_outside_tenant_purge():
    makerspace, user = space("purge"), person("purge")
    row, member = staff_row(user, makerspace, "event_manager"), community(user, makerspace)
    flush()
    with pytest.raises(REFUSED), transaction.atomic():
        MakerspaceMembership.staff_tracks.filter(pk=row.pk).delete()
        flush()
    MakerspaceMembership.objects.filter(pk=member.pk).delete()  # community rows may go
    guc("app.tenant_purge_makerspace_id", makerspace.pk)
    MakerspaceMembership.staff_tracks.filter(pk=row.pk).delete()
    flush()


def test_membership_foreign_keys_follow_their_track():
    from apps.machines.models import MachineType, MembershipMachineTypeScope
    from apps.makerspaces.models import MemberProfile

    makerspace, user = space("fks"), person("fks")
    member, staff = community(user, makerspace), staff_row(user, makerspace, "machine_manager")
    flush()
    machine_type = MachineType.objects.create(makerspace=makerspace, name="Laser", slug="laser-ua1")
    MembershipMachineTypeScope.objects.create(membership=staff, machine_type=machine_type)
    flush()
    with pytest.raises(REFUSED), transaction.atomic():
        MembershipMachineTypeScope.objects.create(membership=member, machine_type=machine_type)
        flush()
    with pytest.raises(REFUSED), transaction.atomic():
        MembershipAdditionalRole.objects.create(membership=member, role=makerspace.roles.get(slug="event_manager"))
        flush()
    with pytest.raises(REFUSED), transaction.atomic():
        MemberProfile.objects.create(membership=staff)
        flush()


def test_completed_merge_records_are_append_only_except_the_purge_scrub():
    user = person("record")
    record = AccountMergeRecord.objects.create(
        decision="converted", source=user, proof_method="migration", run_id=uuid.uuid4(),
        snapshot_scheme="deployment", snapshot_ciphertext="fernet:x", state="completed",
        completed_at=timezone.now())
    with pytest.raises(REFUSED), transaction.atomic():
        AccountMergeRecord.objects.filter(pk=record.pk).update(held_fields=["email"])
    with pytest.raises(REFUSED), transaction.atomic():
        AccountMergeRecord.objects.filter(pk=record.pk).delete()
    scrub = {"snapshot_scheme": "scrubbed", "snapshot_ciphertext": "", "snapshot_key_version": None}
    with pytest.raises(REFUSED), transaction.atomic():
        AccountMergeRecord.objects.filter(pk=record.pk).update(**scrub)
    guc("app.account_purge_user_id", user.pk)
    AccountMergeRecord.objects.filter(pk=record.pk).update(**scrub)
