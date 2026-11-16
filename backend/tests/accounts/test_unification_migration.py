"""The A+2 conversion, run directly on a head database seeded back to its pre-A+2 state.

No migrate-back (X-8): the test drops the validated context check, inserts R1-shaped staff
accounts with the shell-insert guard disabled, re-adds the check NOT VALID exactly as
A+1 leaves it, and then calls the migration's RunPython function.
"""

import importlib
import json
from datetime import timedelta
from types import SimpleNamespace

import pytest
from django.apps import apps as django_apps
from django.db import connection
from django.utils import timezone

from apps.accounts import rbac
from apps.accounts.models import AccountMergeRecord, StaffInvitation, User
from apps.accounts.unification_plan import build_plan
from apps.audit.models import AuditLog
from apps.backup.models import DeploymentRecoveryState
from apps.makerspaces.models import MakerspaceMembership
from apps.makerspaces.secrets import decrypt_value, encrypt_value

from .account_factories import device_grant
from .ua1_helpers import flush, person, space, sql

pytestmark = pytest.mark.django_db
convert = importlib.import_module("apps.accounts.migrations._0050_conversion").convert


def _legacy_staff(template, makerspace, username, email, phone="", role_slug="space_manager", extra=()):
    fields = [field for field in User._meta.concrete_fields if not field.primary_key]
    payload = {field.column: getattr(template, field.attname) for field in fields}
    payload.update(username=username, email=email, phone_e164=phone, account_kind="staff",
                   staff_makerspace_id=makerspace.pk, role="requester", is_active=True,
                   email_verified_at=timezone.now(), credential_generation=3)
    columns = ", ".join(f'"{column}"' for column in payload)
    sql(f"INSERT INTO accounts_user ({columns}) VALUES ({', '.join(['%s'] * len(payload))})",
        list(payload.values()))
    return User.objects.get(username=username)


@pytest.fixture
def r1_database():
    a, b = space("conv-a"), space("conv-b")
    alice, member = person("alice", phone_e164="+15550001"), person("member")
    flush()
    definition = sql("SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conname = 'user_account_context'")[0][0]
    sql("ALTER TABLE accounts_user DROP CONSTRAINT user_account_context")
    sql("ALTER TABLE accounts_user DISABLE TRIGGER accounts_user_context_immutable")
    staff = {
        "s1": _legacy_staff(alice, a, "s1", "ALICE@example.test", phone="+15550001"),
        "s2": _legacy_staff(alice, b, "s2", "s2@example.test", role_slug="inventory_manager"),
        "s3": _legacy_staff(alice, b, "s3", "shared@example.test"),
        "s4": _legacy_staff(alice, a, "s4", "shared@example.test"),
    }
    flush()
    sql("ALTER TABLE accounts_user ENABLE TRIGGER accounts_user_context_immutable")
    sql(f"ALTER TABLE accounts_user ADD CONSTRAINT user_account_context {definition} NOT VALID")
    roles = {"s1": (a, "space_manager", ()), "s2": (b, "inventory_manager", ("event_manager",)),
             "s3": (b, "space_manager", ()), "s4": (a, "event_manager", ())}
    for key, (makerspace, slug, extra) in roles.items():
        row = MakerspaceMembership.staff_tracks.create(
            user=staff[key], makerspace=makerspace, track="staff", role="custom",
            assigned_role=makerspace.roles.get(slug=slug))
        for extra_slug in extra:
            row.additional_roles.create(role=makerspace.roles.get(slug=extra_slug))
    invitation = StaffInvitation.objects.create(
        account=staff["s2"], makerspace=b, email_ciphertext=encrypt_value("s2@example.test"),
        role=b.roles.get(slug="inventory_manager"), token_digest="d" * 64,
        expires_at=timezone.now() + timedelta(days=3), created_by=alice)
    grant = device_grant(member)
    return SimpleNamespace(a=a, b=b, alice=alice, member=member, staff=staff,
                           invitation=invitation, grant=grant)


def _run(settings, ack):
    settings.ACCOUNT_UNIFICATION_ACK = ack
    convert(django_apps, SimpleNamespace(connection=connection))


def test_conversion_refuses_without_the_reviewed_plan(r1_database, settings):
    with pytest.raises(RuntimeError, match="ACCOUNT_UNIFICATION_ACK"):
        _run(settings, "not-the-plan")
    assert User.objects.get(username="s2").account_kind == "staff"
    # Leave a valid database for the commit-time constraint check at teardown.
    _run(settings, build_plan(connection)["plan_sha256"])


def test_conversion_turns_staff_into_people_keeping_roles(r1_database, settings):
    generation = DeploymentRecoveryState.load().auth_generation
    plan = build_plan(connection)
    assert {row["username"]: row["holds"] for row in plan["staff_accounts"]} == {
        "s1": ["email", "phone_e164"], "s2": [], "s3": ["email"], "s4": ["email"]}
    _run(settings, plan["plan_sha256"])
    sql("ALTER TABLE accounts_user VALIDATE CONSTRAINT user_account_context")
    s1, s2 = User.objects.get(username="s1"), User.objects.get(username="s2")
    for user in User.objects.filter(username__in=["s1", "s2", "s3", "s4"]):
        assert user.account_kind == "member" and user.staff_makerspace_id is None
        assert user.email_verified_at is None and user.credential_generation == 4
        assert not MakerspaceMembership.objects.filter(user=user).exists()  # no community row (#66)
    assert (s1.email, s1.phone_e164) == ("", "") and s2.email == "s2@example.test"
    assert User.objects.get(username="alice").email == "alice@example.test"
    assert rbac.is_space_manager_identity(s1, r1_database.a.pk)
    assert rbac.can(s2, rbac.Action.EDIT_INVENTORY, r1_database.b.pk)
    assert rbac.can(s2, rbac.Action.MANAGE_EVENTS, r1_database.b.pk)
    record = AccountMergeRecord.objects.get(source=s1)
    assert (record.decision, record.state, record.held_fields) == ("converted", "completed", ["email", "phone_e164"])
    assert json.loads(decrypt_value(record.snapshot_ciphertext))["email"] == "ALICE@example.test"
    assert AuditLog.objects.filter(action="account.converted").count() == 4
    r1_database.grant.refresh_from_db()
    r1_database.invitation.refresh_from_db()
    assert r1_database.grant.status == "revoked" and r1_database.invitation.revoked_at is not None
    assert DeploymentRecoveryState.load().auth_generation != generation
    assert build_plan(connection)["staff_accounts"] == []
