"""Release-2 lane L21b (finalists, round panels, programme options, prize payouts) dispositions.

Imported by the programme catalogue files with one explicit line each, as L7's pairwise rows are, so
the programme guards (field snapshot, dataset, authority, uniqueness, purge) see these rows exactly
like the other judging rows. User edges (`created_by`, `published_by`, `recipient`, `recorded_by`)
are classified in `accounts/merge_registry_rows_l21b.py`.
"""

FIELD_NAMES = {
    'events.JudgingPanelSeat': frozenset('id round judge_role_assignment'.split()),
    'events.FinalistAdvance': frozenset(
        'id event source_round target_round selection top_n fingerprint created_by created_at'.split()),
    'events.JudgingFinalist': frozenset('id advance snapshot source_rank'.split()),
    'events.FinalistAnnouncement': frozenset('id event advance published_at published_by'.split()),
    'events.HackathonProgrammeOptions': frozenset(
        'id version event results_email submission_receipt_email finalists_email refund_on_disqualification '
        'entry_fee team_fee updated_at'.split()),
    'events.HackathonPrizePayout': frozenset(
        'id makerspace event award prize recipient kind reverses amount currency method reference paid_on '
        'ledger_entry recorded_by created_at'.split()),
}
#: New columns on existing programme models.
EXTRA_FIELDS = {
    'events.JudgingRound': frozenset({'visibility', 'fresh_eyes', 'advanced_from'}),
    'events.HackathonPrize': frozenset({'amount_per_winner'}),
    'events.JudgeScore': frozenset({'saved_at'}),
}

DATASETS = {
    'events.JudgingPanelSeat': ('events/programme/JudgingPanelSeat.csv', 'round__event__makerspace'),
    'events.FinalistAdvance': ('events/programme/FinalistAdvance.csv', 'event__makerspace'),
    'events.JudgingFinalist': ('events/programme/JudgingFinalist.csv', 'advance__event__makerspace'),
    'events.FinalistAnnouncement': ('events/programme/FinalistAnnouncement.csv', 'event__makerspace'),
    'events.HackathonProgrammeOptions': ('events/programme/HackathonProgrammeOptions.csv', 'event__makerspace'),
    'events.HackathonPrizePayout': ('events/programme/HackathonPrizePayout.csv', 'makerspace'),
}

_DEF = 'Authored round or event configuration; it travels as data and grants no target authority.'
_EVIDENCE = 'Append-only selection or money evidence; preserved, remapped, and never a grant of target authority.'
_REFERENCE = 'Typed subject/attribution reference; remapped retained history alone grants no target authority.'
_SEAT = 'A panel seat names an event judge role; the live judge entitlement, not this row, is the authority.'

AUTHORITY_FIELDS = {
    ('events.JudgingRound', 'visibility'): _DEF, ('events.JudgingRound', 'fresh_eyes'): _DEF,
    ('events.JudgingRound', 'advanced_from'): _REFERENCE, ('events.HackathonPrize', 'amount_per_winner'): _DEF,
    ('events.JudgeScore', 'saved_at'): _EVIDENCE,
    ('events.JudgingPanelSeat', 'round'): _REFERENCE, ('events.JudgingPanelSeat', 'judge_role_assignment'): _SEAT,
    **{('events.FinalistAdvance', name): _EVIDENCE for name in ('selection', 'top_n', 'fingerprint', 'created_at')},
    **{('events.FinalistAdvance', name): _REFERENCE for name in ('event', 'source_round', 'target_round', 'created_by')},
    ('events.JudgingFinalist', 'source_rank'): _EVIDENCE,
    **{('events.JudgingFinalist', name): _REFERENCE for name in ('advance', 'snapshot')},
    ('events.FinalistAnnouncement', 'published_at'): _EVIDENCE,
    **{('events.FinalistAnnouncement', name): _REFERENCE for name in ('event', 'advance', 'published_by')},
    **{('events.HackathonProgrammeOptions', name): _DEF for name in (
        'version', 'results_email', 'submission_receipt_email', 'finalists_email', 'refund_on_disqualification',
        'entry_fee', 'team_fee', 'updated_at')},
    ('events.HackathonProgrammeOptions', 'event'): _REFERENCE,
    **{('events.HackathonPrizePayout', name): _EVIDENCE for name in (
        'kind', 'amount', 'currency', 'method', 'reference', 'paid_on', 'created_at')},
    **{('events.HackathonPrizePayout', name): _REFERENCE for name in (
        'makerspace', 'event', 'award', 'prize', 'recipient', 'reverses', 'ledger_entry', 'recorded_by')},
}

# Panel seats, finalists and programme options are unique per tenant-owned parent (round, advance,
# event), so they carry no deployment-global risk.
UNIQUE_CONSTRAINTS = (
    ('events.FinalistAnnouncement', 'field:advance'),
    ('events.HackathonPrizePayout', 'field:reverses'),
)

# Children first: payouts, announcements, finalists, advances and panel seats all precede their
# JudgingRound / EventAward / SubmissionSnapshot parents.
PURGE_ORDER = (
    ('events.HackathonPrizePayout', 'event__makerspace'),
    ('events.FinalistAnnouncement', 'event__makerspace'),
    ('events.JudgingFinalist', 'advance__event__makerspace'),
    ('events.FinalistAdvance', 'event__makerspace'),
    ('events.JudgingPanelSeat', 'round__event__makerspace'),
    ('events.HackathonProgrammeOptions', 'event__makerspace'),
)
