"""Capability purge plans for lane L3b (decision 223 (k)): superadmin-only, previewed, audited.

* `membership.minors` -- minor records, guardian consents and the consent texts. Accounts and memberships stay.
* `membership.volunteer_credit` -- volunteer hour entries and credits. Charges a credit already reduced stay
  in the payment ledger.
* `bookings.organization_bookings` -- the organization links on bookings. The bookings and their charges stay.
"""


def _minors_delete(space, cursor):
    from .community_purge import delete_minors
    from .module_purge_collectors_single_model import _counts
    count, labels = delete_minors(space)
    return _counts(model_labels=labels, minor_rows=count)


def _volunteer_delete(space, cursor):
    from .community_purge import delete_volunteer
    from .module_purge_collectors_single_model import _counts
    count, labels = delete_volunteer(space)
    return _counts(model_labels=labels, volunteer_rows=count)


def _org_delete(space, cursor):
    from .community_purge import delete_organization_links
    from .module_purge_collectors_single_model import _counts
    count, labels = delete_organization_links(space)
    return _counts(model_labels=labels, organization_links=count)


def _minors_preview(space):
    from .community_purge import preview_minors
    return preview_minors(space)


def _volunteer_preview(space):
    from .community_purge import preview_volunteer
    return preview_volunteer(space)


def _org_preview(space):
    from apps.bookings.models import BookingOrganizationLink, OrganizationHoursAllowance, OrganizationHoursLedger
    return {"organization_links": BookingOrganizationLink.objects.filter(makerspace=space).count(),
            "organization_hours_banks": OrganizationHoursAllowance.objects.filter(makerspace=space).count(),
            "organization_hours_ledger_rows": OrganizationHoursLedger.objects.filter(makerspace=space).count()}


def plans(plan):
    return (
        plan("membership.minors", "Minor records, guardian consents and consent texts. Accounts and memberships stay.",
             _minors_delete, _minors_preview),
        plan("membership.volunteer_credit", "Volunteer hour entries and credits. Charges already reduced stay in "
             "the payment ledger.", _volunteer_delete, _volunteer_preview),
        plan("bookings.organization_bookings", "Organization links on bookings. The bookings and their charges stay.",
             _org_delete, _org_preview),
    )
