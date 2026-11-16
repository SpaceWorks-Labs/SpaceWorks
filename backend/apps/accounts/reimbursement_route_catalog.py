"""Literal reimbursement, stage-form and core payout route/method inventory.

Classification opens no permission: every view still authorizes the actor, live host,
module and finance/reauth requirements itself. Names are explicit so a new route stays
unclassified (and refused) until it is reviewed here.
"""

# Surface: "member" = owner routes under /api/v1/member/ (full sessions only);
# "delegable" = event-scoped staff routes an event grant may reach (the view still checks
# the exact event permission); "membership" = finance/host routes that need a live
# makerspace membership with VIEW_FINANCE and are never delegable.
# Target: "event" resolves pk -> Event host; "tenant" is the makerspace_id path segment;
# "obligation" resolves obligation_id -> payout host; "account" has no tenant target.
# (bare Django name, methods, target kind, surface)
ROUTES = (
    ('member-event-payout-list', ('GET', 'HEAD'), 'account', 'member'),
    ('member-event-payout-detail', ('GET', 'HEAD'), 'obligation', 'member'),
    ('member-event-payout-payee', ('DELETE', 'GET', 'HEAD', 'PUT'), 'obligation', 'member'),
    ('member-event-payee-reveal', ('POST',), 'obligation', 'member'),
    ('member-event-payee-file-create', ('GET', 'HEAD', 'POST'), 'obligation', 'member'),
    ('member-event-payee-file-detail', ('DELETE', 'GET', 'HEAD'), 'obligation', 'member'),
    ('member-event-payee-file-complete', ('POST',), 'obligation', 'member'),
    ('finance-event-payout-list', ('GET', 'HEAD'), 'tenant', 'membership'),
    ('finance-event-payout-dashboard', ('GET', 'HEAD'), 'tenant', 'membership'),
    ('finance-event-payout-export', ('POST',), 'tenant', 'membership'),
    ('finance-event-payout-export-download', ('GET', 'HEAD'), 'tenant', 'membership'),
    ('finance-event-payout-detail', ('GET', 'HEAD'), 'tenant', 'membership'),
    ('finance-event-payout-record', ('POST',), 'tenant', 'membership'),
    ('finance-event-payout-amend', ('POST',), 'tenant', 'membership'),
    ('finance-event-payout-cancel', ('POST',), 'tenant', 'membership'),
    ('finance-event-payee-verify', ('POST',), 'tenant', 'membership'),
    ('finance-event-payee-request-correction', ('POST',), 'tenant', 'membership'),
    ('finance-event-payee-reveal', ('POST',), 'tenant', 'membership'),
    ('finance-event-payout-hold', ('POST',), 'tenant', 'membership'),
    ('finance-event-payout-release-hold', ('POST',), 'tenant', 'membership'),
    ('finance-event-payout-acknowledge-eligibility', ('POST',), 'tenant', 'membership'),
    ('finance-event-attachment-download', ('GET', 'HEAD'), 'tenant', 'membership'),
    ('admin-event-stage-form-list', ('GET', 'HEAD', 'POST'), 'event', 'delegable'),
    ('admin-event-stage-form-detail', ('GET', 'HEAD', 'PATCH'), 'event', 'delegable'),
    ('admin-event-stage-form-publish', ('POST',), 'event', 'delegable'),
    ('admin-event-stage-form-retire', ('POST',), 'event', 'delegable'),
    ('admin-event-stage-form-activate', ('POST',), 'event', 'delegable'),
    ('admin-event-stage-assignment-list', ('GET', 'HEAD'), 'event', 'delegable'),
    ('admin-event-stage-assignment-cancel', ('POST',), 'event', 'delegable'),
    ('admin-event-stage-assignment-reassign', ('POST',), 'event', 'delegable'),
    ('admin-event-stage-assignment-extend', ('POST',), 'event', 'delegable'),
    ('admin-event-stage-assignment-reopen', ('POST',), 'event', 'delegable'),
    ('admin-event-stage-shortlist', ('POST',), 'event', 'delegable'),
    ('admin-event-stage-response-detail', ('GET', 'HEAD'), 'event', 'delegable'),
    ('admin-event-stage-response-finance-detail', ('GET', 'HEAD'), 'event', 'membership'),
    ('admin-event-stage-file-download', ('GET', 'HEAD'), 'event', 'delegable'),
    ('member-event-stage-form-list', ('GET', 'HEAD'), 'event', 'member'),
    ('member-event-stage-form-context', ('GET', 'HEAD'), 'event', 'member'),
    ('member-event-stage-draft', ('POST',), 'event', 'member'),
    ('member-event-stage-response', ('GET', 'HEAD', 'PUT'), 'event', 'member'),
    ('member-event-stage-response-submit', ('POST',), 'event', 'member'),
    ('member-event-stage-file-create', ('POST',), 'event', 'member'),
    ('member-event-stage-file-detail', ('DELETE', 'GET', 'HEAD'), 'event', 'member'),
    ('member-event-stage-file-complete', ('POST',), 'event', 'member'),
    ('member-event-stage-file-download', ('GET', 'HEAD'), 'event', 'member'),
    ('member-event-reimbursement', ('GET', 'HEAD', 'POST'), 'event', 'member'),
    ('member-event-reimbursement-request-submit', ('POST',), 'event', 'member'),
    ('member-event-reimbursement-request-withdraw', ('POST',), 'event', 'member'),
    ('member-event-reimbursement-award-accept', ('POST',), 'event', 'member'),
    ('member-event-reimbursement-award-decline', ('POST',), 'event', 'member'),
    ('member-event-reimbursement-claim', ('GET', 'HEAD', 'PUT'), 'event', 'member'),
    ('member-event-reimbursement-claim-submit', ('POST',), 'event', 'member'),
    ('member-event-reimbursement-claim-appeal', ('POST',), 'event', 'member'),
    ('member-event-receipt-file-create', ('POST',), 'event', 'member'),
    ('member-event-receipt-file-detail', ('DELETE', 'GET', 'HEAD'), 'event', 'member'),
    ('member-event-receipt-file-complete', ('POST',), 'event', 'member'),
    ('admin-event-reimbursement-programme', ('GET', 'HEAD', 'PATCH', 'POST'), 'event', 'membership'),
    ('admin-event-reimbursement-request-list', ('GET', 'HEAD'), 'event', 'delegable'),
    ('admin-event-reimbursement-request-decide', ('POST',), 'event', 'delegable'),
    ('admin-event-reimbursement-crew-pool', ('POST',), 'event', 'membership'),  # hack-money G14
    ('admin-event-reimbursement-staff-claim', ('POST',), 'event', 'delegable'),  # parity C17
    ('admin-event-reimbursement-direct-booking', ('POST',), 'event', 'membership'),  # hack-money G12
    ('admin-event-reimbursement-direct-booking-cancel', ('POST',), 'event', 'membership'),
    ('admin-event-reimbursement-claim-list', ('GET', 'HEAD'), 'event', 'delegable'),
    ('admin-event-reimbursement-claim-detail', ('GET', 'HEAD'), 'event', 'delegable'),
    ('admin-event-reimbursement-claim-review', ('POST',), 'event', 'delegable'),
    ('admin-event-reimbursement-claim-extend', ('POST',), 'event', 'membership'),
    ('admin-event-reimbursement-attendance-attest', ('POST',), 'event', 'membership'),
    ('admin-event-reimbursement-receipt-override', ('POST',), 'event', 'membership'),
    ('admin-event-reimbursement-claim-correct-decision', ('POST',), 'event', 'membership'),
)

BY_NAME = {name: (methods, target, surface) for name, methods, target, surface in ROUTES}
