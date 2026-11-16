"""Fixtures for the unified-accounts tests (one account per person, U-A1)."""

import uuid

from django.db import connection, transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.makerspaces.models import Makerspace, MakerspaceMembership


def sql(statement, params=()):
    with connection.cursor() as cursor:
        cursor.execute(statement, params)
        return cursor.fetchall() if cursor.description else None


def flush():
    """Fire every deferred constraint trigger now, then defer again."""
    sql("SET CONSTRAINTS ALL IMMEDIATE")
    sql("SET CONSTRAINTS ALL DEFERRED")


def guc(name, value):
    sql("SELECT set_config(%s, %s, true)", [name, str(value)])


def space(slug):
    return Makerspace.objects.create(name=slug, slug=slug)


def person(username, **fields):
    fields.setdefault("email", f"{username}@example.test")
    return User.objects.create_user(username, **fields)


def platform(username="root"):
    return User.objects.create_superuser(username, f"{username}@example.test", "pw-strong-123")


def community(user, makerspace, *, status="active"):
    role = makerspace.roles.get(slug="member")
    return MakerspaceMembership.objects.create(
        user=user, makerspace=makerspace, assigned_role=role, role="custom", status=status)


def staff_row(user, makerspace, role_slug="space_manager", *, status="active", extra=()):
    role = makerspace.roles.get(slug=role_slug)
    with transaction.atomic():
        row = MakerspaceMembership.staff_tracks.create(
            user=user, makerspace=makerspace, track="staff", assigned_role=role,
            role=role.legacy_role or "custom", status=status)
        for slug in extra:
            row.additional_roles.create(role=makerspace.roles.get(slug=slug))
    return row


def merged_shell(source, survivor):
    """Turn ``source`` into a shell merged into ``survivor`` the way U-C's engine will."""
    guc("app.account_unification_run_id", uuid.uuid4())
    User.objects.filter(pk=source.pk).update(
        account_kind="staff", merged_into=survivor, merged_at=timezone.now(), is_active=False,
        username=f"merged-{uuid.uuid4().hex}")
    guc("app.account_unification_run_id", "")
    source.refresh_from_db()
    return source
