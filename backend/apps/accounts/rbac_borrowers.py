"""Owner scope for borrowing data, including spaces with account-only borrowing."""


def _eligible_borrower(borrower, makerspace):
    from apps.accounts.models import User
    from apps.makerspaces.servability import is_servable

    return bool(borrower and borrower.is_authenticated and borrower.is_active
                and not borrower.is_tenant_dump_stub
                and borrower.access_status == User.AccessStatus.ACTIVE and is_servable(makerspace))


def scope_by_borrower(borrower, queryset, *, makerspace, owner_field="requester", field="makerspace_id"):
    if not _eligible_borrower(borrower, makerspace):
        return queryset.none()
    # Borrowers never get staff rows. Membership-module admission is a separate gate
    # at the workflow boundary; an account-only space still has owner-scoped loans.
    return queryset.filter(**{field: makerspace.pk, owner_field: borrower})


def scope_personal_borrowing(actor, queryset, *, makerspace):
    """Own READ history includes merged shells without widening any workflow mutation."""
    from django.utils.translation import gettext
    from rest_framework.exceptions import PermissionDenied
    from .account_kind_guards import require_member_account
    from .rbac_notifications import personal_notification_membership_refused
    from .staff_identity import actor_ids_for

    require_member_account(actor)
    if (not _eligible_borrower(actor, makerspace) or actor.is_walk_in
            or personal_notification_membership_refused(actor, makerspace.pk)):
        raise PermissionDenied(gettext("An active, unrestricted account is required."))
    return queryset.filter(makerspace_id=makerspace.pk, requester_id__in=actor_ids_for(actor))
