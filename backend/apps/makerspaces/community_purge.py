"""Decision 223 (k), lane L3b: what a purge removes of the minors, volunteer and community-policy tables.

The whole-tenant purge reaches `module_delete` through `membership_delete`; organization links cascade from the
booking and the space.

Consents PROTECT their terms and cascade from profiles, so consents go first, then profiles, then terms.
`Payment` rows a credit reduced are ledger money and are never touched (CLAUDE.md: the ledger is core);
a credit's `applied_payment` is SET_NULL. Booking organization links are removed with the `bookings`
capability or module, not here.
"""


def _minor_querysets(makerspace):
    from apps.makerspaces.models import GuardianConsent, GuardianConsentTerms, MinorProfile
    return (GuardianConsent.objects.filter(makerspace=makerspace), MinorProfile.objects.filter(makerspace=makerspace),
            GuardianConsentTerms.objects.filter(makerspace=makerspace))


def _volunteer_querysets(makerspace):
    from apps.makerspaces.models import VolunteerCredit, VolunteerHourEntry
    return (VolunteerCredit.objects.filter(makerspace=makerspace), VolunteerHourEntry.objects.filter(makerspace=makerspace))


def delete_minors(makerspace):
    from apps.makerspaces.module_purge_collectors_single_model import _delete
    count, labels = 0, frozenset()
    for queryset in _minor_querysets(makerspace):
        deleted, model_labels = _delete(queryset)
        count, labels = count + deleted, labels | model_labels
    return count, labels


def delete_volunteer(makerspace):
    from apps.makerspaces.module_purge_collectors_single_model import _delete
    count, labels = 0, frozenset()
    for queryset in _volunteer_querysets(makerspace):
        deleted, model_labels = _delete(queryset)
        count, labels = count + deleted, labels | model_labels
    return count, labels


def module_delete(makerspace):
    """`(rows_deleted, model_labels)` for the membership module purge: minors, volunteer rows and the policy."""
    from apps.makerspaces.models import CommunityPolicy
    from apps.makerspaces.module_purge_collectors_single_model import _delete
    minors, minor_labels = delete_minors(makerspace)
    volunteer, volunteer_labels = delete_volunteer(makerspace)
    policies, policy_labels = _delete(CommunityPolicy.objects.filter(makerspace=makerspace))
    return minors + volunteer + policies, minor_labels | volunteer_labels | policy_labels


def delete_organization_links(makerspace):
    from apps.bookings.models import BookingOrganizationLink, OrganizationHoursAllowance, OrganizationHoursLedger
    from apps.makerspaces.module_purge_collectors_single_model import _delete
    # B13: the organization hours bank goes with the organization bookings it serves.
    ledger, ledger_labels = _delete(OrganizationHoursLedger.objects.filter(makerspace=makerspace))
    banks, bank_labels = _delete(OrganizationHoursAllowance.objects.filter(makerspace=makerspace))
    links, link_labels = _delete(BookingOrganizationLink.objects.filter(makerspace=makerspace))
    return ledger + banks + links, ledger_labels | bank_labels | link_labels


def preview_minors(makerspace):
    consents, profiles, terms = _minor_querysets(makerspace)
    return {"minor_profiles": profiles.count(), "guardian_consents": consents.count(), "guardian_terms": terms.count()}


def preview_volunteer(makerspace):
    credits, entries = _volunteer_querysets(makerspace)
    return {"volunteer_hour_entries": entries.count(), "volunteer_credits": credits.count()}
