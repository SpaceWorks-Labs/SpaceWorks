"""Schema-only rollback of 0089, refused whenever it would lose or misstate authority.

The forward step cannot be undone in place: custom roles it deleted are gone. What CAN be
rolled back safely is a database where nothing yet relies on the fixed catalogue -- every
remaining role row is then a valid pre-upgrade row, and the only rows 0089 added are the
three new built-ins, which nothing references. Anything else (an additional role, a
per-person machine link, or any reference to a new built-in) refuses, and the operator
restores the pre-upgrade backup instead.
"""

from django.db.migrations.exceptions import IrreversibleError

NEW_SLUGS = ("event_manager", "booking_manager", "handover")
_REFERENCES = (
    ("makerspaces.MakerspaceMembership", "assigned_role"),
    ("makerspaces.MembershipRequest", "assigned_role"),
    ("accounts.StaffInvitation", "role"),
    ("integrations.NotificationRecipient", "role"),
)


def reverse_fixed_roles(apps, alias):
    def rows(label):
        return apps.get_model(label).objects.using(alias)

    new_roles = rows("makerspaces.MakerspaceRole").filter(slug__in=NEW_SLUGS)
    blocked = (
        rows("makerspaces.MembershipAdditionalRole").exists()
        or rows("machines.MembershipMachineTypeScope").exists()
        or any(rows(label).filter(**{f"{field}__in": new_roles}).exists()
               for label, field in _REFERENCES)
        or any(rows("operations.ReportSchedule").filter(recipient_roles__contains=[slug]).exists()
               for slug in NEW_SLUGS)
    )
    if blocked:
        raise IrreversibleError(
            "Fixed-role migration cannot be reversed; restore the pre-upgrade backup."
        )
    new_roles.delete()
