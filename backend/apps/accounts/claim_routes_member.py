"""Claim policies for member and membership routes."""

from django.utils.translation import gettext_lazy
from apps.accounts.claim_route_types import (
    AnonymousRead,
    Allowed,
    ID,
    LocallyFiltered,
    ReadOnly,
    Refused,
    RowOwnership,
)


def _options(name):
    return {(name, "OPTIONS"): AnonymousRead()}


MEMBER_CLAIM_ROUTES = {
    **{(name, method): Refused(gettext_lazy("claim sessions cannot manage admission applications"))
       for name, methods in (
           ("member-admission", ("GET", "HEAD")),
           ("member-admission-export", ("GET", "HEAD")),
           ("member-admission-cancel", ("POST",)),
           ("member-admission-vouch", ("POST",)),
       ) for method in methods},
    **{(name, "OPTIONS"): AnonymousRead() for name in (
        "member-admission", "member-admission-export", "member-admission-cancel", "member-admission-vouch",
    )},
    **{(name, method): Refused(gettext_lazy("claim sessions cannot manage an account or end membership"))
       for name, methods in (
           ("member-account-profile", ("GET", "HEAD", "PATCH")),
           ("member-account-sessions", ("GET", "HEAD")),
           ("member-account-session-detail", ("DELETE",)),
           ("member-account-membership", ("GET", "HEAD")),
           ("member-account-cancel", ("POST",)),
           ("member-account-leave", ("POST",)),
           ("member-subject-export-list", ("GET", "HEAD", "POST")),
           ("member-subject-export-detail", ("GET", "HEAD")),
           ("member-subject-export-download", ("POST",)),
       ) for method in methods},
    **{(name, "OPTIONS"): AnonymousRead() for name in (
        "member-account-profile", "member-account-sessions", "member-account-session-detail",
        "member-account-membership", "member-account-cancel", "member-account-leave",
        "member-subject-export-list", "member-subject-export-detail", "member-subject-export-download",
    )},
    ("member-archived-payments", "GET"): Refused(
        gettext_lazy("tenantless archived-payment discovery cannot satisfy single tenancy"),
        ownership=RowOwnership.MIXED_REFUSED,
    ),
    ("member-archived-payments", "HEAD"): Refused(
        gettext_lazy("tenantless archived-payment discovery cannot satisfy single tenancy"),
        ownership=RowOwnership.MIXED_REFUSED,
    ),
    **_options("member-archived-payments"),
    ("my-memberships", "GET"): Refused(gettext_lazy("the membership list spans tenants")),
    ("my-memberships", "HEAD"): Refused(gettext_lazy("the membership list spans tenants")),
    **_options("my-memberships"),
    ("membership-invitations", "GET"): Refused(gettext_lazy("claim sessions cannot claim invitations")),
    ("membership-invitations", "HEAD"): Refused(gettext_lazy("claim sessions cannot claim invitations")),
    **_options("membership-invitations"),
    ("membership-invitation-claim", "POST"): Refused(gettext_lazy("claim sessions cannot claim invitations")),
    **_options("membership-invitation-claim"),
    ("membership-invitation-claim-legacy", "POST"): Refused(
        gettext_lazy("claim sessions cannot claim invitations")
    ),
    **_options("membership-invitation-claim-legacy"),
    ("member-waiver", "GET"): ReadOnly(tenant=ID),
    ("member-waiver", "HEAD"): ReadOnly(tenant=ID),
    **_options("member-waiver"),
    ("member-waiver-accept", "POST"): Refused(
        gettext_lazy("claim waiver acceptance must be witnessed by authenticated staff")
    ),
    **_options("member-waiver-accept"),
    ("member-certifications", "GET"): ReadOnly(tenant=ID),
    ("member-certifications", "HEAD"): ReadOnly(tenant=ID),
    **_options("member-certifications"),
    # Owner self-service on a machine-service job (C4/C16): one explicit entry per route
    # and method, no fallback. Row ownership is `member_id == caller`; a claim session
    # is never the job's owner account, so both are refused outright.
    ("member-machine-service-cancel", "POST"): Refused(
        gettext_lazy("claim sessions cannot cancel machine-service jobs"), ownership=RowOwnership.SINGLE_OWNER,
    ),
    **_options("member-machine-service-cancel"),
    ("member-machine-service-owner", "GET"): Refused(
        gettext_lazy("claim sessions cannot read machine-service owner controls"), ownership=RowOwnership.SINGLE_OWNER,
    ),
    ("member-machine-service-owner", "HEAD"): Refused(
        gettext_lazy("claim sessions cannot read machine-service owner controls"), ownership=RowOwnership.SINGLE_OWNER,
    ),
    **_options("member-machine-service-owner"),
    ("member-activity", "GET"): LocallyFiltered(tenant=ID),
    ("member-activity", "HEAD"): LocallyFiltered(tenant=ID),
    **_options("member-activity"),
    ("member-my-usage", "GET"): LocallyFiltered(tenant=ID),
    ("member-my-usage", "HEAD"): LocallyFiltered(tenant=ID),
    **_options("member-my-usage"),
    ("hardware_requests:member-loan-renew", "POST"): Allowed(
        tenant=ID, audited=True, ownership=RowOwnership.LOCAL_OWNER_ENFORCED,
    ),
    **_options("hardware_requests:member-loan-renew"),
    ("member-payment-history", "GET"): LocallyFiltered(tenant=ID),
    ("member-payment-history", "HEAD"): LocallyFiltered(tenant=ID),
    **_options("member-payment-history"),
    # Document metadata uses the same claim-local payment queryset as history.
    ("member-payment-documents", "GET"): LocallyFiltered(tenant=ID),
    ("member-payment-documents", "HEAD"): LocallyFiltered(tenant=ID),
    **_options("member-payment-documents"),
    # The PDF endpoint lies outside the bounded claim surface and needs an ordinary
    # account session. Do not mint a grant that the claim holder cannot redeem.
    ("member-payment-document-url", "GET"): Refused(gettext_lazy("PDF downloads require an account session")),
    ("member-payment-document-url", "HEAD"): Refused(gettext_lazy("PDF downloads require an account session")),
    **_options("member-payment-document-url"),
    ("member-payment-checkout", "POST"): Allowed(
        tenant=ID,
        audited=True,
        ownership=RowOwnership.LOCAL_OWNER_ENFORCED,
    ),
    **_options("member-payment-checkout"),
    ("member-payment-mobile-intent", "POST"): Refused(
        gettext_lazy("native payment intent requires an attested device grant")
    ),
    **_options("member-payment-mobile-intent"),
    # A refund request is a money decision on the account's own ledger; a walk-in
    # claim session at a kiosk must not open or withdraw one.
    ("member-refund-request", "POST"): Refused(gettext_lazy("refund requests require an account session")),
    **_options("member-refund-request"),
    ("member-refund-withdraw", "POST"): Refused(gettext_lazy("refund requests require an account session")),
    **_options("member-refund-withdraw"),
    ("member-referrals", "POST"): Refused(gettext_lazy("walk-ins cannot delegate membership eligibility")),
    **_options("member-referrals"),
    ("member-verification", "POST"): Refused(gettext_lazy("claim sessions cannot verify other members")),
    **_options("member-verification"),
    # Profile payloads include event activity. D5 applies the claim-local event filter;
    # D3 records that mixed ownership so it cannot be mistaken for a plain local read.
    ("member-profile", "GET"): LocallyFiltered(tenant=ID),
    ("member-profile", "HEAD"): LocallyFiltered(tenant=ID),
    ("member-profile", "PUT"): Allowed(
        tenant=ID, audited=True, ownership=RowOwnership.LOCALLY_FILTERED
    ),
    **_options("member-profile"),
    ("member-profile-image", "POST"): Allowed(tenant=ID, audited=False),
    ("member-profile-image", "PUT"): Allowed(
        tenant=ID, audited=True, ownership=RowOwnership.LOCALLY_FILTERED
    ),
    ("member-profile-image", "DELETE"): Allowed(
        tenant=ID, audited=True, ownership=RowOwnership.LOCALLY_FILTERED
    ),
    **_options("member-profile-image"),
    # Member ID cards (forward plan phase 5): same rule as the calendar-feed bearer token —
    # a walk-in claim session never holds or edits a durable credential.
    ("member-card", "GET"): Refused(
        gettext_lazy("a member card is a durable physical credential; claim sessions cannot read or manage it")
    ),
    ("member-card", "HEAD"): Refused(
        gettext_lazy("a member card is a durable physical credential; claim sessions cannot read or manage it")
    ),
    ("member-card", "PATCH"): Refused(
        gettext_lazy("a member card is a durable physical credential; claim sessions cannot read or manage it")
    ),
    **_options("member-card"),
    ("member-card-photo", "POST"): Refused(
        gettext_lazy("a member card is a durable physical credential; claim sessions cannot read or manage it")
    ),
    ("member-card-photo", "PUT"): Refused(
        gettext_lazy("a member card is a durable physical credential; claim sessions cannot read or manage it")
    ),
    ("member-card-photo", "DELETE"): Refused(
        gettext_lazy("a member card is a durable physical credential; claim sessions cannot read or manage it")
    ),
    **_options("member-card-photo"),
    ("member-card-preview", "GET"): Refused(
        gettext_lazy("a member card is a durable physical credential; claim sessions cannot read or manage it")
    ),
    ("member-card-preview", "HEAD"): Refused(
        gettext_lazy("a member card is a durable physical credential; claim sessions cannot read or manage it")
    ),
    **_options("member-card-preview"),
    ("member-directory", "GET"): ReadOnly(tenant=ID),
    ("member-directory", "HEAD"): ReadOnly(tenant=ID),
    **_options("member-directory"),
    ("member-directory-detail", "GET"): LocallyFiltered(tenant=ID),
    ("member-directory-detail", "HEAD"): LocallyFiltered(tenant=ID),
    **_options("member-directory-detail"),
    ("member-collaborative-events", "GET"): Refused(
        gettext_lazy("collaborative event lists contain foreign-owned rows"),
        ownership=RowOwnership.MIXED_REFUSED,
    ),
    ("member-collaborative-events", "HEAD"): Refused(
        gettext_lazy("collaborative event lists contain foreign-owned rows"),
        ownership=RowOwnership.MIXED_REFUSED,
    ),
    **_options("member-collaborative-events"),
    ("member-collaborative-event-register", "POST"): Refused(
        gettext_lazy("collaborative registration can create a foreign-owned row"),
        ownership=RowOwnership.MIXED_REFUSED,
    ),
    **_options("member-collaborative-event-register"),
    ("member-event-registration-cancel", "POST"): Refused(
        gettext_lazy("event cancellation can mutate a foreign-hosted registration"),
        ownership=RowOwnership.MIXED_REFUSED,
    ),
    **_options("member-event-registration-cancel"),
    ("member-event-checkin-qr", "GET"): Refused(
        gettext_lazy("event QR resolution can return foreign-owned registration rows"),
        ownership=RowOwnership.MIXED_REFUSED,
    ),
    ("member-event-checkin-qr", "HEAD"): Refused(
        gettext_lazy("event QR resolution can return foreign-owned registration rows"),
        ownership=RowOwnership.MIXED_REFUSED,
    ),
    **_options("member-event-checkin-qr"),
    **{(name, method): Refused(
        gettext_lazy("event tickets can contain foreign-hosted registrations and durable QR credentials"),
        ownership=RowOwnership.MIXED_REFUSED,
    ) for name in ("member-event-ticket", "member-event-ticket-png")
       for method in ("GET", "HEAD")},
    **_options("member-event-ticket"),
    **_options("member-event-ticket-png"),
    **{("member-event-registration-calendar", method): Refused(
        gettext_lazy("registration calendars can contain foreign-hosted rows"),
        ownership=RowOwnership.MIXED_REFUSED,
    ) for method in ("GET", "HEAD")},
    **_options("member-event-registration-calendar"),
    ("member-event-calendar", "GET"): Refused(
        gettext_lazy("event calendars can contain foreign-hosted registration rows"),
        ownership=RowOwnership.MIXED_REFUSED,
    ),
    ("member-event-calendar", "HEAD"): Refused(
        gettext_lazy("event calendars can contain foreign-hosted registration rows"),
        ownership=RowOwnership.MIXED_REFUSED,
    ),
    **_options("member-event-calendar"),
    ("member-event-calendar-feed", "GET"): Refused(
        gettext_lazy("claim sessions cannot manage durable bearer credentials")
    ),
    # DRF derives HEAD from GET, so the pair must be declared together or the route is
    # half-classified and the matrix guard fails.
    ("member-event-calendar-feed", "HEAD"): Refused(
        gettext_lazy("claim sessions cannot manage durable bearer credentials")
    ),
    ("member-event-calendar-feed", "POST"): Refused(
        gettext_lazy("claim sessions cannot manage durable bearer credentials")
    ),
    ("member-event-calendar-feed", "DELETE"): Refused(
        gettext_lazy("claim sessions cannot manage durable bearer credentials")
    ),
    **_options("member-event-calendar-feed"),
    ("member-event-feedback", "GET"): Refused(
        gettext_lazy("event feedback can return foreign-hosted registration rows"),
        ownership=RowOwnership.MIXED_REFUSED,
    ),
    ("member-event-feedback", "HEAD"): Refused(
        gettext_lazy("event feedback can return foreign-hosted registration rows"),
        ownership=RowOwnership.MIXED_REFUSED,
    ),
    ("member-event-feedback", "POST"): Refused(
        gettext_lazy("event feedback can write a foreign-hosted response"),
        ownership=RowOwnership.MIXED_REFUSED,
    ),
    **_options("member-event-feedback"),
    ("member-event-certificate-download", "GET"): Refused(
        gettext_lazy("event certificates can belong to foreign-hosted registrations"),
        ownership=RowOwnership.MIXED_REFUSED,
    ),
    ("member-event-certificate-download", "HEAD"): Refused(
        gettext_lazy("event certificates can belong to foreign-hosted registrations"),
        ownership=RowOwnership.MIXED_REFUSED,
    ),
    **_options("member-event-certificate-download"),
}

# Release 2 L5: telling a space you paid a charge offline is a money statement on the
# account's own ledger; a walk-in claim session at a kiosk must not make one.
MEMBER_CLAIM_ROUTES.update({
    ("member-paid-claim", "POST"): Refused(gettext_lazy("offline payment claims require an account session")),
    **_options("member-paid-claim"),
})
