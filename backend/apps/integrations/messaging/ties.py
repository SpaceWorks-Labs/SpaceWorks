"""Derived member-audience ties; consent never creates a tie of its own."""
from apps.accounts.models import User
from apps.integrations.recipients_owners import owner_accounts, owner_membership, owns_tenant_row


def has_tenant_tie(user, makerspace):
    if not user or not user.is_authenticated or not user.pk:
        return False
    if not owner_accounts().filter(pk=user.pk, deletion_requested_at__isnull=True,
                                  is_superuser=False, account_kind="member").exclude(role=User.Role.SUPERADMIN).exists():
        return False
    membership = owner_membership(makerspace, user.pk)
    if membership is not None:
        # Revocation wins over every old loan, booking, registration and charge.
        return membership.status == "active"
    return owns_tenant_row(makerspace, user.pk)
