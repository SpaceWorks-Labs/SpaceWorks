"""Release-2 lane L7 (pairwise judging) schema, dump, authority, uniqueness and purge dispositions.

Imported by the programme catalogue files with one explicit line each, so the existing programme
guards see these models exactly like the other judging rows. No `accounts.User` edge: the judge is
an `events.EventRoleAssignment`.
"""

FIELD_NAMES = {
    'events.JudgePairwiseComparison': frozenset(
        'id version outcome notes submitted_at sequence makerspace event round judge previous current'.split()),
    'events.JudgePairwiseInvalidation': frozenset('id created_at comparison reason'.split()),
    'events.JudgePairwiseCursor': frozenset('id version draw_count updated_at event round judge previous current'.split()),
}

DATASETS = {
    'events.JudgePairwiseComparison': ('events/programme/JudgePairwiseComparison.csv', 'event__makerspace'),
    'events.JudgePairwiseInvalidation': ('events/programme/JudgePairwiseInvalidation.csv', 'comparison__event__makerspace'),
    'events.JudgePairwiseCursor': ('events/programme/JudgePairwiseCursor.csv', 'event__makerspace'),
}

_EVIDENCE = 'Authored definition or historical workflow evidence; preserved behind reset operational gates and live target authority.'
_REFERENCE = 'Typed subject/attribution reference; remapped retained history alone grants no target authority.'
_PRIVATE = 'Private historical evidence; disclosure stays owner/permission scoped and sensitive sources stay encrypted.'
_OPERATIONAL = 'Operational judging cursor; it only orders what a judge sees next and grants no target authority.'

AUTHORITY_FIELDS = {
    **{('events.JudgePairwiseComparison', name): _EVIDENCE for name in ('version', 'outcome', 'submitted_at', 'sequence', 'makerspace')},
    **{('events.JudgePairwiseComparison', name): _REFERENCE for name in ('event', 'round', 'judge', 'previous', 'current')},
    ('events.JudgePairwiseComparison', 'notes'): _PRIVATE,
    ('events.JudgePairwiseInvalidation', 'created_at'): _EVIDENCE,
    ('events.JudgePairwiseInvalidation', 'comparison'): _REFERENCE,
    ('events.JudgePairwiseInvalidation', 'reason'): _REFERENCE,
    **{('events.JudgePairwiseCursor', name): _OPERATIONAL for name in
       ('version', 'draw_count', 'updated_at', 'event', 'round', 'judge', 'previous', 'current')},
}

_REMAP = "Typed owners, canonical object keys or reconstructed coordination keys follow the target allocation; duplicate tuples refuse."
# `JudgePairwiseInvalidation.comparison` is its tenant ownership path
# (comparison__event__makerspace), so its one-to-one uniqueness is tenant-scoped, not a risk.
UNIQUE_CONSTRAINTS = (
    ('events.JudgePairwiseComparison', 'ev_pairwise_sequence'),
    ('events.JudgePairwiseComparison', 'ev_pairwise_pair_once'),
    ('events.JudgePairwiseCursor', 'ev_pairwise_cursor_once'),
)

# Children first: invalidations, then comparisons and cursors, all before JudgeAssignment/JudgingRound.
PURGE_ORDER = (
    ('events.JudgePairwiseInvalidation', 'comparison__event__makerspace'),
    ('events.JudgePairwiseCursor', 'event__makerspace'),
    ('events.JudgePairwiseComparison', 'event__makerspace'),
)
