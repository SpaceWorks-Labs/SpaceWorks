"""Claim policies for release-2 routes on claim-reachable prefixes: U-C's account merge and
L12's machine jobs, loan waitlist and request withdrawal; L23's machine sessions; #196's
access tokens and app connections; the public paused-space state.

A claim session (a walk-in claiming an account at a kiosk) never merges accounts, never
acts on a member's own job, waitlist or request, and never submits a job; the public job
types list ignores a presented claim token.
"""

from apps.accounts.claim_route_types import AnonymousRead, Refused

_REFUSED = (
    ("claim sessions cannot read account borrowing history", (
        ("hardware_requests:member-borrowing-history", ("GET", "HEAD")),
    )),
    ("claim sessions cannot merge accounts", (
        ("auth-account-merge-start", ("POST",)), ("auth-account-merge-prove", ("POST",)),
        ("auth-account-merge-resend", ("POST",)), ("auth-account-merge-preview", ("GET", "HEAD")),
        ("auth-account-merge-confirm", ("POST",)), ("auth-account-merge-cancel", ("POST",)),
        ("auth-account-merge-passkey-options", ("POST",)),
    )),
    ("claim sessions cannot read or act on machine jobs", (
        ("member-machine-jobs", ("GET", "HEAD")), ("member-machine-job-detail", ("GET", "HEAD")),
        ("member-machine-job-approve-quote", ("POST",)), ("member-machine-job-decline-quote", ("POST",)),
        ("member-machine-job-resubmit", ("POST",)), ("member-machine-job-consumables", ("POST",)),
        ("public-machine-job-upload", ("POST",)), ("public-machine-job-submit", ("POST",)),
        ("member-machine-use-events", ("GET", "HEAD")),
    )),
    ("claim sessions cannot start, stop or read machine sessions", (
        ("member-machine-session-preview", ("GET", "HEAD")), ("member-machine-session-start", ("POST",)),
        ("member-machine-sessions", ("GET", "HEAD")), ("member-machine-session-stop", ("POST",)),
    )),
    ("claim sessions cannot lead supervised sessions or list member machines", (
        ("member-machines", ("GET", "HEAD")), ("member-machine-access", ("GET", "HEAD")),
        ("member-machine-type-guide", ("GET", "HEAD")), ("member-machine-type-document-url", ("GET", "HEAD")),
        ("member-supervised-session-open", ("POST",)),
        ("member-supervised-sessions", ("GET", "HEAD")), ("member-supervised-session", ("GET", "HEAD")),
        ("member-supervised-supervisees", ("POST",)), ("member-supervised-supervisee-remove", ("DELETE",)),
        ("member-supervised-people", ("GET", "HEAD")), ("member-supervised-use-start", ("POST",)),
        ("member-supervised-use-end", ("POST",)), ("member-supervised-session-close", ("POST",)),
    )),
    ("claim sessions cannot report or read incidents (L3a)", (("member-incidents", ("GET", "HEAD", "POST")),)),
    ("claim sessions cannot report problems or read reports (L16)", (
        ("member-issues", ("GET", "HEAD", "POST")), ("member-issue-photo-upload", ("POST",)),
        ("member-issue-loan-items", ("GET", "HEAD")),
        ("public-issue-report", ("POST",)), ("public-issue-photo-upload", ("POST",)),
        ("public-technician-opt-in", ("GET", "HEAD", "POST")),
    )),
    ("claim sessions cannot manage loan waitlists or withdraw requests", (
        ("hardware_requests:member-loan-waitlist", ("GET", "HEAD", "POST")),
        ("hardware_requests:member-loan-waitlist-leave", ("POST",)),
        ("hardware_requests:member-request-withdraw", ("POST",)),
    )),
    # #196 (gap-api): personal access tokens and app connections are a person's own credentials.
    ("claim sessions cannot mint, read or revoke access tokens or app connections", (
        ("auth-access-tokens", ("GET", "HEAD", "POST")), ("auth-access-token-revoke", ("DELETE",)),
        ("auth-access-token-scopes", ("GET", "HEAD")), ("auth-oauth-consent", ("GET", "HEAD", "POST")),
        ("auth-connected-apps", ("GET", "HEAD")), ("auth-connected-app-revoke", ("DELETE",)),
    )),
)

R2_CLAIM_ROUTES = {
    **{(name, method): Refused(reason)
       for reason, routes in _REFUSED for name, methods in routes for method in methods},
    **{(name, "OPTIONS"): AnonymousRead()
       for _reason, routes in _REFUSED for name, _methods in routes},
    **{("public-machine-job-types", method): AnonymousRead() for method in ("GET", "HEAD", "OPTIONS")},
    # Superadmin controls: the paused/active state of a public space has no authentication classes.
    **{("public-makerspace-availability", method): AnonymousRead() for method in ("GET", "HEAD", "OPTIONS")},
}
