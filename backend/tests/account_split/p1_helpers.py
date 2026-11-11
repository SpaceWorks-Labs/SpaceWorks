"""Explicit principal factories; never retrofit staff authority onto a member."""

from django.db import connection, transaction

from apps.accounts.models import User
from apps.makerspaces.models import MakerspaceMembership


def staff(space, username="staff", role="inventory_manager", **fields):
    with transaction.atomic():
        # One account per person (U-A1): a person holding a staff-track row.
        user = User.objects.create_user(username, **fields)
        membership = MakerspaceMembership.staff_tracks.create(
            user=user, makerspace=space, role=role, track="staff", assigned_role=space.roles.get(slug=role),
        )
    return user, membership


def sql(statement, params=()):
    with connection.cursor() as cursor:
        cursor.execute(statement, params)


def flush_constraints():
    sql("SET CONSTRAINTS ALL IMMEDIATE")
    sql("SET CONSTRAINTS ALL DEFERRED")


def raw_membership(template, **overrides):
    fields = [field for field in MakerspaceMembership._meta.concrete_fields if not field.primary_key]
    values = {field.column: getattr(template, field.attname) for field in fields}
    values.update(overrides)
    columns = ", ".join(f'"{column}"' for column in values)
    sql(f"INSERT INTO makerspaces_makerspacemembership ({columns}) VALUES ({', '.join(['%s'] * len(values))})",
        list(values.values()))
