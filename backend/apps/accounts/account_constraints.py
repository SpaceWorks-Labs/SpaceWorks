"""Database constraints for one account per person, platform accounts and inert shells."""

from django.db import models
from django.db.models import F, Q
from django.db.models.functions import Lower

# Live accounts are people (``member``) or platform. A ``staff`` row is an inert shell:
# a legacy retired staff account or an account merged into a person. Shells hold no
# tenant, never sign in, and keep their primary key for immutable history.
ACCOUNT_CONTEXT = (
    (Q(account_kind="staff", staff_makerspace__isnull=True, is_active=False)
     & (Q(retired_at__isnull=False) | Q(merged_into__isnull=False)))
    | Q(account_kind__in=["member", "platform"], staff_makerspace__isnull=True,
        retired_at__isnull=True, merged_into__isnull=True)
)
MERGE_STAMP = (Q(merged_into__isnull=True, merged_at__isnull=True)
               | Q(merged_into__isnull=False, merged_at__isnull=False))


def user_constraints():
    return [
        models.CheckConstraint(condition=ACCOUNT_CONTEXT, name="user_account_context"),
        models.CheckConstraint(condition=MERGE_STAMP, name="user_merge_stamp"),
        models.CheckConstraint(condition=~Q(merged_into=F("id")), name="user_not_merged_into_self"),
        models.CheckConstraint(
            condition=(Q(account_kind="platform", is_superuser=True, role="superadmin")
                       | (Q(account_kind__in=["member", "staff"], is_superuser=False)
                          & ~Q(role="superadmin"))),
            name="user_platform_flags",
        ),
        models.CheckConstraint(condition=(Q(account_kind="member") | Q(
            deletion_requested_at__isnull=True, deletion_purge_after__isnull=True,
            purge_started_at__isnull=True, account_restored_at__isnull=True,
            account_purged_at__isnull=True, deletion_email_ciphertext="", deletion_username="",
        )), name="user_member_lifecycle"),
        # One address per person. Phone and Telegram identities stay person-scoped too.
        models.UniqueConstraint(Lower("email"), condition=Q(account_kind="member") & ~Q(email=""),
                                name="uniq_person_email"),
        models.UniqueConstraint(Lower("email"), condition=Q(account_kind="platform") & ~Q(email=""),
                                name="uniq_platform_email"),
        *[
            models.UniqueConstraint(fields=[field], condition=Q(account_kind="member") & ~Q(**{field: ""}),
                                    name=name)
            for field, name in (
                ("phone_e164", "uniq_member_phone_e164"),
                ("telegram_user_id", "uniq_member_telegram_id"),
            )
        ],
    ]
