"""Hack-money lane (#180, #181) dispositions for the events programme catalogue.

Imported by the programme catalogue files with one explicit line each, after L21b's, so the
programme guards (field snapshot, dataset, authority, uniqueness, purge) see these rows exactly
like the other judging rows. User edges are classified in `accounts/merge_registry_rows_hackmoney.py`.
A prize claim's payee details and PAN are always-encrypted scoped PII and travel only as envelopes.
"""

_DEF = 'Authored round or event configuration; it travels as data and grants no target authority.'
_EVIDENCE = 'Append-only money or selection evidence; preserved, remapped, and never a grant of target authority.'
_REFERENCE = 'Typed subject/attribution reference; remapped retained history alone grants no target authority.'
_CLAIM = 'A winner\'s own payee details and tax ID, encrypted; they decide nothing on the target.'

FIELD_NAMES = {
    'events.HackathonPrizeShare': frozenset(
        'id event version makerspace award member amount state proposed_by confirmed_at created_at'.split()),
    'events.HackathonPrizeClaim': frozenset(
        'id event version makerspace share country method template_key details pan submitted_at verified_at '
        'verified_by cleared_at'.split()),
    'events.HackathonPrizeOutcome': frozenset(
        'id makerspace event award share payout resolves kind method reference amount currency happened_on note '
        'ledger_entry recorded_by created_at'.split()),
}
#: New columns on existing programme models.
EXTRA_FIELDS = {
    'events.HackathonProgrammeOptions': frozenset({'refund_on_withdrawal', 'refund_if_not_shortlisted',
                                                   'show_prize_amounts', 'prize_claim_days', 'deposit_amount',
                                                   'deposit_requires_submission', 'deposits_settled_at'}),
    'events.HackathonPrize': frozenset({'kind', 'value_text', 'estimated_value', 'funding'}),
    'events.HackathonPrizePayout': frozenset({'tds_amount', 'net_amount'}),
}
DATASETS = {
    'events.HackathonPrizeShare': ('events/programme/HackathonPrizeShare.csv', 'makerspace'),
    'events.HackathonPrizeClaim': ('events/programme/HackathonPrizeClaim.csv', 'makerspace'),
    'events.HackathonPrizeOutcome': ('events/programme/HackathonPrizeOutcome.csv', 'makerspace'),
}
#: Account edges exported as personal references; the portable closure carries each named person.
USER_FIELDS = frozenset({('events.HackathonPrizeShare', 'member'), ('events.HackathonPrizeShare', 'proposed_by'),
                         ('events.HackathonPrizeClaim', 'verified_by'), ('events.HackathonPrizeOutcome', 'recorded_by')})
AUTHORITY_FIELDS = {
    **{('events.HackathonProgrammeOptions', name): _DEF for name in (
        'refund_on_withdrawal', 'refund_if_not_shortlisted', 'show_prize_amounts', 'prize_claim_days',
        'deposit_amount', 'deposit_requires_submission')},
    ('events.HackathonProgrammeOptions', 'deposits_settled_at'): _EVIDENCE,
    **{('events.HackathonPrize', name): _DEF for name in ('kind', 'value_text', 'estimated_value', 'funding')},
    **{('events.HackathonPrizePayout', name): _EVIDENCE for name in ('tds_amount', 'net_amount')},
    **{('events.HackathonPrizeShare', name): _EVIDENCE for name in (
        'version', 'amount', 'state', 'confirmed_at', 'created_at')},
    **{('events.HackathonPrizeShare', name): _REFERENCE for name in (
        'event', 'makerspace', 'award', 'member', 'proposed_by')},
    **{('events.HackathonPrizeClaim', name): _CLAIM for name in (
        'version', 'country', 'method', 'template_key', 'details', 'pan', 'submitted_at', 'verified_at',
        'cleared_at')},
    **{('events.HackathonPrizeClaim', name): _REFERENCE for name in ('event', 'makerspace', 'share', 'verified_by')},
    **{('events.HackathonPrizeOutcome', name): _EVIDENCE for name in (
        'kind', 'method', 'reference', 'amount', 'currency', 'happened_on', 'note', 'created_at')},
    **{('events.HackathonPrizeOutcome', name): _REFERENCE for name in (
        'makerspace', 'event', 'award', 'share', 'payout', 'resolves', 'ledger_entry', 'recorded_by')},
}
# Shares are unique per (award, member) and claims per share: both remap with their parents.
UNIQUE_CONSTRAINTS = (
    ('events.HackathonPrizeShare', 'ev_prize_share_member'),
    ('events.HackathonPrizeClaim', 'field:share'),
    ('events.HackathonPrizeOutcome', 'field:resolves'),
)
# Children first: outcomes point at payouts and shares; claims at shares; shares at awards.
PURGE_ORDER = (
    ('events.HackathonPrizeOutcome', 'makerspace'),
    ('events.HackathonPrizeClaim', 'makerspace'),
    ('events.HackathonPrizeShare', 'makerspace'),
)
