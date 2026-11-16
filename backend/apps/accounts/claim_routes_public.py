"""Claim policies for routes mounted below ``/api/v1/public/``."""

from django.utils.translation import gettext_noop
from apps.accounts.claim_route_types import (
    AnonymousRead,
    Allowed,
    BODY_OBJECT,
    PUBLIC_TOKEN,
    ReadOnly,
    Refused,
    SLUG,
)


def _anonymous(name):
    return {
        (name, "GET"): AnonymousRead(),
        (name, "HEAD"): AnonymousRead(),
        (name, "OPTIONS"): AnonymousRead(),
    }


PUBLIC_CLAIM_ROUTES = {
    **_anonymous("public-booking-resource"),
    **_anonymous("public-booking-website"),
    **_anonymous("public-booking-website-image"),
    **{(name, method): Refused(gettext_noop("claim sessions cannot read or rotate account arrival credentials"))
       for name, methods in (
           ("member-booking-confirmation", ("GET", "HEAD")),
           ("member-booking-confirmation-png", ("GET", "HEAD")),
           ("member-booking-calendar", ("GET", "HEAD")),
           ("member-booking-pass", ("GET", "HEAD")),
           ("member-booking-rotate-checkin", ("POST",)),
       ) for method in methods},
    **{(name, "OPTIONS"): AnonymousRead() for name in (
        "member-booking-confirmation", "member-booking-confirmation-png",
        "member-booking-calendar", "member-booking-rotate-checkin", "member-booking-pass",
    )},
    ('member-booking-reschedule', 'POST'): Allowed(tenant=SLUG, audited=True),
    ('member-booking-reschedule', 'OPTIONS'): AnonymousRead(),
    **{('member-booking-feed-settings', method): Refused(
        gettext_noop('claim sessions cannot manage durable bearer credentials')
    ) for method in ('GET', 'HEAD', 'POST', 'DELETE')},
    ('member-booking-feed-settings', 'OPTIONS'): AnonymousRead(),
    **_anonymous('public-booking-feed'),
    ('member-booking-list', 'GET'): ReadOnly(tenant=SLUG),
    ('member-booking-list', 'HEAD'): ReadOnly(tenant=SLUG),
    ('member-booking-list', 'OPTIONS'): AnonymousRead(),
    ('member-booking-cancel', 'POST'): Allowed(tenant=SLUG, audited=True),
    ('member-booking-cancel', 'OPTIONS'): AnonymousRead(),
    ('member-booking-checkout', 'POST'): Allowed(tenant=SLUG, audited=True),
    ('member-booking-checkout', 'OPTIONS'): AnonymousRead(),
    **_anonymous("public-event-venue"),
    **_anonymous("public-membership-admission"),
    **_anonymous("public-member-units"),  # parity O-B1: the join page unit picker
    **_anonymous("public-machines"),
    **_anonymous("public-machine-intake"),
    **_anonymous("public-machine-details"),
    **_anonymous("public-machine-detail"),
    ("public-machine-service-request-submit", "POST"): Allowed(
        tenant=BODY_OBJECT, audited=True
    ),
    ("public-machine-service-request-submit", "OPTIONS"): AnonymousRead(),
    **_anonymous("public-printer-service-queues"),
    **_anonymous("public-printer-service-pools"),
    ("public-printer-service-upload", "POST"): Allowed(tenant=SLUG, audited=True),
    ("public-printer-service-upload", "OPTIONS"): AnonymousRead(),
    ("public-printer-service-request", "POST"): Allowed(tenant=SLUG, audited=True),
    ("public-printer-service-request", "OPTIONS"): AnonymousRead(),
    **_anonymous("public-printer-service-status"),
    **_anonymous("public-machine-service-status"),
    **_anonymous("public-event-list"),
    **_anonymous("public-event-detail"),
    **_anonymous("public-event-share-image"),
    **_anonymous("public-event-website"),
    **_anonymous("public-event-website-section"),
    **_anonymous("public-event-website-speaker"),
    **_anonymous("public-event-website-session"),
    **_anonymous("public-event-website-schedule"),
    **_anonymous("public-event-website-image"),
    **{("public-event-organization-eligibility", method): Refused(
        gettext_noop("organization eligibility requires an account session")
    ) for method in ("GET", "HEAD")},
    ("public-event-organization-eligibility", "OPTIONS"): AnonymousRead(),
    # The organization directory is deployment-global read-only presentation; a walk-in
    # claim session reads it exactly like any anonymous visitor.
    **_anonymous("public-organization-detail"),
    **_anonymous("public-organization-directory"),
    **_anonymous("public-organization-events"),
    **_anonymous("public-event-calendar"),
    **_anonymous("public-event-calendar-feed"),
    ("public-event-register", "POST"): Allowed(
        tenant=PUBLIC_TOKEN, audited=True
    ),
    ("public-event-register", "OPTIONS"): AnonymousRead(),
    **_anonymous("public-event-feedback"),
    ("public-event-feedback", "POST"): Allowed(
        tenant=PUBLIC_TOKEN, audited=True
    ),
    **_anonymous("public-bookable-space-list"),
    **_anonymous("public-space-availability"),
    ("public-booking-submit", "POST"): Allowed(
        tenant=PUBLIC_TOKEN, audited=True
    ),
    ("public-booking-submit", "OPTIONS"): AnonymousRead(),
    ("presence-start", "POST"): Allowed(tenant=SLUG, audited=True),
    ("presence-start", "OPTIONS"): AnonymousRead(),
    ("presence-current", "GET"): ReadOnly(tenant=SLUG),
    ("presence-current", "HEAD"): ReadOnly(tenant=SLUG),
    ("presence-current", "OPTIONS"): AnonymousRead(),
    ("presence-end", "POST"): Allowed(tenant=SLUG, audited=True),
    ("presence-end", "OPTIONS"): AnonymousRead(),
    **_anonymous("v1:public-makerspaces"),
    **_anonymous("v1:public-inventory"),
    **_anonymous("v1:public-makerspace-stats"),
    **_anonymous("v1:public-inventory-categories"),
    **_anonymous("v1:public-inventory-detail"),
    ("v1:public-inventory-watch", "POST"): Allowed(tenant=SLUG, audited=True),
    ("v1:public-inventory-watch", "DELETE"): Allowed(tenant=SLUG, audited=True),
    ("v1:public-inventory-watch", "OPTIONS"): AnonymousRead(),
    ("public-membership-request", "POST"): Refused(
        gettext_noop("walk-ins cannot satisfy verified-email eligibility")
    ),
    ("public-membership-request", "OPTIONS"): AnonymousRead(),
    # A walk-in already holds a membership claim; asking to be invited makes no sense
    # from inside one, and the anonymous path stays open to everyone else.
    ("public-invitation-request", "POST"): Refused(
        gettext_noop("walk-ins already hold a membership; invitation requests are for outsiders")
    ),
    ("public-invitation-request", "OPTIONS"): AnonymousRead(),
    # Hosting a makerspace is platform-level and anonymous; a walk-in's claim session
    # has no business applying on anyone's behalf.
    **{(name, method): policy
       for name in ("public-hosting-request-submit", "public-hosting-request-open", "public-hosting-request-resubmit",
                    "public-hosting-invitation-resolve", "public-hosting-invitation-submit")
       for method, policy in (
           ("POST", Refused(gettext_noop("claim sessions cannot apply to host a makerspace"))),
           ("OPTIONS", AnonymousRead()),
       )},
    ("hardware_requests:request-submit", "POST"): Allowed(
        tenant=SLUG, audited=True
    ),
    ("hardware_requests:request-submit", "OPTIONS"): AnonymousRead(),
    ("hardware_requests:request-contact-code", "POST"): Allowed(
        tenant=SLUG, audited=True
    ),
    ("hardware_requests:request-contact-code", "OPTIONS"): AnonymousRead(),
    ("hardware_requests:public-tool-evidence-url", "POST"): Allowed(
        tenant=SLUG, audited=True
    ),
    ("hardware_requests:public-tool-evidence-url", "OPTIONS"): AnonymousRead(),
    ("hardware_requests:public-tool-checklist", "POST"): Allowed(
        tenant=SLUG, audited=False
    ),
    ("hardware_requests:public-tool-checklist", "OPTIONS"): AnonymousRead(),
    ("hardware_requests:public-tool-checkout", "POST"): Allowed(
        tenant=SLUG, audited=True
    ),
    ("hardware_requests:public-tool-checkout", "OPTIONS"): AnonymousRead(),
    ("hardware_requests:public-tool-return", "POST"): Allowed(
        tenant=SLUG, audited=True
    ),
    ("hardware_requests:public-tool-return", "OPTIONS"): AnonymousRead(),
    **_anonymous("hardware_requests:request-status"),
    # Published equipment kits are a signed-in member read of the slug's tenant; the
    # contextual self-request writes exactly like request-submit.
    **{(name, method): ReadOnly(tenant=SLUG)
       for name in ("hardware_requests:equipment-kit-public-list", "hardware_requests:equipment-kit-public-detail")
       for method in ("GET", "HEAD")},
    ("hardware_requests:equipment-kit-public-list", "OPTIONS"): AnonymousRead(),
    ("hardware_requests:equipment-kit-public-detail", "OPTIONS"): AnonymousRead(),
    ("hardware_requests:contextual-request-self", "POST"): Allowed(tenant=SLUG, audited=True),
    ("hardware_requests:contextual-request-self", "OPTIONS"): AnonymousRead(),
}

# Release 2 L5 pay links: the link itself is the only credential. The views carry no
# authentication classes, so a presented claim token is ignored, never used.
PUBLIC_CLAIM_ROUTES.update({
    **_anonymous("pay-link"),
    ("pay-link-claim", "POST"): AnonymousRead(),
    ("pay-link-claim", "OPTIONS"): AnonymousRead(),
    ("pay-link-checkout", "POST"): AnonymousRead(),
    ("pay-link-checkout", "OPTIONS"): AnonymousRead(),
})

# Release 2 L15: the price preview. A claim session is quoted the public price; only an
# account session reads the member's own price.
PUBLIC_CLAIM_ROUTES.update({
    ("pricing-quote", "POST"): AnonymousRead(),
    ("pricing-quote", "OPTIONS"): AnonymousRead(),
})
