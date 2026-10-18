"""Reviewed programme dynamic audit namespaces; metadata is denied by default."""
EXACT = frozenset(('account_pii.keys_erased', 'account_pii.keys_revoked', 'event.contributor_notice.delivered', 'event.contributor_notice.retry', 'event.mentor_notice.delivered', 'event.mentor_notice.retry', 'event.badge_design_saved', 'event.certificate_template_saved'))
NON_LITERAL = frozenset(('event.form_revised', 'notification.media_grant_consumed', 'notification.media_grant_issued'))
WRAPPERS = {
    'events/answer_derivations/workflow.py': ('event.',),
    'events/contributions/commands.py': ('event.',),
    'events/hackathons/admission_transactions.py': ('event.',),
    'events/judging/boundary.py': ('event.',),
    'events/mentoring/help_expiry.py': ('event.',),
    'events/programme/broadcast_schedule.py': ('event.',),
    'events/submissions/asset_workflow.py': ('event.',),
    'events/submissions/workflow.py': ('event.',),
}
