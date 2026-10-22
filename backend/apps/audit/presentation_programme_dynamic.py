"""Reviewed programme dynamic audit namespaces; metadata is denied by default."""
EXACT = frozenset(('account_pii.keys_erased', 'account_pii.keys_revoked', 'event.contributor_notice.delivered', 'event.contributor_notice.retry', 'event.mentor_notice.delivered', 'event.mentor_notice.retry', 'event.badge_design_saved', 'event.certificate_template_saved'))
# Event reimbursements, staged forms and finance payouts choose these by branch.
EXACT |= frozenset(('event.stage_form.draft_saved', 'event.stage_form.submitted', 'finance.attachment.cleanup_complete', 'finance.attachment.cleanup_retry', 'finance.attachment.duplicate', 'finance.attachment.held', 'finance.attachment.hold_released', 'finance.attachment.ready', 'finance.event_payout.amended', 'finance.event_payout.held', 'finance.event_payout.hold_released', 'finance.event_payout.payee_correction', 'finance.event_payout.payee_verified', 'finance.event_payout.recorded'))
NON_LITERAL = frozenset(('event.form_revised',))
WRAPPERS = {
    'events/answer_derivations/workflow.py': ('event.',),
    'events/contributions/commands.py': ('event.',),
    'events/hackathons/admission_transactions.py': ('event.',),
    'events/judging/boundary.py': ('event.',),
    'events/mentoring/help_expiry.py': ('event.',),
    'events/programme/broadcast_schedule.py': ('event.',),
    'events/submissions/asset_workflow.py': ('event.',),
    'events/submissions/workflow.py': ('event.',),
    'events/staged_forms/transactions.py': ('event.',),
}
