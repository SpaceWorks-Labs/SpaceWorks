"""Claim policies for release-2 routes on claim-reachable prefixes: U-C's account merge and
L12's machine jobs, loan waitlist and request withdrawal.

A claim session (a walk-in claiming an account at a kiosk) never merges accounts, never
acts on a member's own job, waitlist or request, and never submits a job; the public job
types list ignores a presented claim token.
"""

from apps.accounts.claim_route_types import AnonymousRead, Refused

_REFUSED = (
    ("claim sessions cannot merge accounts", (
        ("auth-account-merge-start", ("POST",)), ("auth-account-merge-prove", ("POST",)),
        ("auth-account-merge-resend", ("POST",)), ("auth-account-merge-preview", ("GET", "HEAD")),
        ("auth-account-merge-confirm", ("POST",)), ("auth-account-merge-cancel", ("POST",)),
    )),
    ("claim sessions cannot read or act on machine jobs", (
        ("member-machine-jobs", ("GET", "HEAD")), ("member-machine-job-detail", ("GET", "HEAD")),
        ("member-machine-job-approve-quote", ("POST",)), ("member-machine-job-decline-quote", ("POST",)),
        ("member-machine-job-resubmit", ("POST",)),
        ("public-machine-job-upload", ("POST",)), ("public-machine-job-submit", ("POST",)),
    )),
    ("claim sessions cannot manage loan waitlists or withdraw requests", (
        ("hardware_requests:member-loan-waitlist", ("GET", "HEAD", "POST")),
        ("hardware_requests:member-loan-waitlist-leave", ("POST",)),
        ("hardware_requests:member-request-withdraw", ("POST",)),
    )),
)

R2_CLAIM_ROUTES = {
    **{(name, method): Refused(reason)
       for reason, routes in _REFUSED for name, methods in routes for method in methods},
    **{(name, "OPTIONS"): AnonymousRead()
       for _reason, routes in _REFUSED for name, _methods in routes},
    **{("public-machine-job-types", method): AnonymousRead() for method in ("GET", "HEAD", "OPTIONS")},
}
