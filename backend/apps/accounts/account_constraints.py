"""Database constraints for immutable account contexts and scoped identities."""

from django.db import models
from django.db.models import F, Q
from django.db.models.functions import Lower


def user_constraints():
    return [
        models.CheckConstraint(
            condition=(
                Q(account_kind="staff", staff_makerspace__isnull=False, retired_at__isnull=True)
                | Q(account_kind="staff", staff_makerspace__isnull=True,
                    retired_at__isnull=False, is_active=False)
                | Q(account_kind__in=["member", "platform"],
                    staff_makerspace__isnull=True, retired_at__isnull=True)
            ), name="user_account_context",
        ),
        models.CheckConstraint(
            condition=(Q(account_kind="platform", is_superuser=True, role="superadmin")
                       | (Q(account_kind__in=["member", "staff"], is_superuser=False)
                          & ~Q(role="superadmin"))),
            name="user_platform_flags",
        ),
        models.UniqueConstraint(Lower("email"), condition=Q(account_kind="member") & ~Q(email=""),
                                name="uniq_member_email"),
        models.UniqueConstraint(Lower("email"), F("staff_makerspace"),
                                condition=Q(account_kind="staff") & ~Q(email=""),
                                name="uniq_staff_space_email"),
        models.UniqueConstraint(Lower("email"), condition=Q(account_kind="platform") & ~Q(email=""),
                                name="uniq_platform_email"),
        *[
            models.UniqueConstraint(fields=[field], condition=Q(account_kind="member") & ~Q(**{field: ""}),
                                    name=name)
            for field, name in (
                ("phone_e164", "uniq_member_phone_e164"),
                ("telegram_user_id", "uniq_member_telegram_id"),
                ("external_checkin_user_id", "uniq_member_checkin_id"),
            )
        ],
    ]
