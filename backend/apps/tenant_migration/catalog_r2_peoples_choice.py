"""Lane r2-peoples-choice (#181 S3) dispositions: config, ballots, the published result and standings.

Imported by the programme catalogue files with one explicit line each, as L21b's rows are, so the
programme guards (field snapshot, dataset, authority, uniqueness, purge) see these rows exactly like
the other judging rows. User edges (`voter`, `voided_by`, `published_by`) are classified in
`accounts/merge_registry_rows_peoples_choice.py`.
"""

FIELD_NAMES = {
    'events.PeoplesChoiceConfig': frozenset(
        'id version event enabled audience opens_at closes_at prize open_email updated_at'.split()),
    'events.PeoplesChoiceVote': frozenset(
        'id event voter team handle version cast_at changed_at voided_at void_reason voided_by'.split()),
    'events.PeoplesChoiceResult': frozenset(
        'id event prize prize_name total_votes published_at published_by'.split()),
    'events.PeoplesChoiceStanding': frozenset('id result submission_snapshot votes rank winner'.split()),
}
#: New columns on existing programme models.
EXTRA_FIELDS = {
    'events.HackathonPrizePayout': frozenset({'peoples_choice_standing'}),
}

DATASETS = {
    'events.PeoplesChoiceConfig': ('events/programme/PeoplesChoiceConfig.csv', 'event__makerspace'),
    'events.PeoplesChoiceVote': ('events/programme/PeoplesChoiceVote.csv', 'event__makerspace'),
    'events.PeoplesChoiceResult': ('events/programme/PeoplesChoiceResult.csv', 'event__makerspace'),
    'events.PeoplesChoiceStanding': ('events/programme/PeoplesChoiceStanding.csv', 'result__event__makerspace'),
}

_DEF = 'Authored event configuration; it travels as data and grants no target authority.'
_BALLOT = 'A member ballot is evidence of a vote; it travels as data and grants no target authority.'
_EVIDENCE = 'Append-only award evidence; preserved, remapped, and never a grant of target authority.'
_REFERENCE = 'Typed subject/attribution reference; remapped retained history alone grants no target authority.'

AUTHORITY_FIELDS = {
    **{('events.PeoplesChoiceConfig', name): _DEF for name in (
        'version', 'enabled', 'audience', 'opens_at', 'closes_at', 'open_email', 'updated_at')},
    **{('events.PeoplesChoiceConfig', name): _REFERENCE for name in ('event', 'prize')},
    **{('events.PeoplesChoiceVote', name): _BALLOT for name in (
        'handle', 'version', 'cast_at', 'changed_at', 'voided_at')},
    **{('events.PeoplesChoiceVote', name): _REFERENCE for name in (
        'event', 'voter', 'team', 'void_reason', 'voided_by')},
    **{('events.PeoplesChoiceResult', name): _EVIDENCE for name in ('prize_name', 'total_votes', 'published_at')},
    **{('events.PeoplesChoiceResult', name): _REFERENCE for name in ('event', 'prize', 'published_by')},
    **{('events.PeoplesChoiceStanding', name): _EVIDENCE for name in ('votes', 'rank', 'winner')},
    **{('events.PeoplesChoiceStanding', name): _REFERENCE for name in ('result', 'submission_snapshot')},
    ('events.HackathonPrizePayout', 'peoples_choice_standing'): _REFERENCE,
}

# Every unique key here includes the row's tenant root (event, or result for standings), so none is a
# deployment-global risk: the uniqueness guard needs no rule.
UNIQUE_CONSTRAINTS = ()

# Children first: standings precede their result; ballots, results and configs precede the teams,
# snapshots, prizes and reasons they point at. Payouts (L21b) are purged before standings.
PURGE_ORDER = (
    ('events.PeoplesChoiceStanding', 'result__event__makerspace'),
    ('events.PeoplesChoiceResult', 'event__makerspace'),
    ('events.PeoplesChoiceVote', 'event__makerspace'),
    ('events.PeoplesChoiceConfig', 'event__makerspace'),
)
