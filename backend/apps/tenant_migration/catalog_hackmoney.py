"""Hack-money lane (#180) dispositions for the events programme catalogue.

Imported by the programme catalogue files with one explicit line each, after L21b's, so the
programme guards (field snapshot, dataset, authority, uniqueness, purge) see these rows exactly
like the other judging rows. User edges are classified in `accounts/merge_registry_rows_hackmoney.py`.
"""

_DEF = 'Authored round or event configuration; it travels as data and grants no target authority.'

FIELD_NAMES = {}
#: New columns on existing programme models.
EXTRA_FIELDS = {
    'events.HackathonProgrammeOptions': frozenset({'refund_on_withdrawal', 'refund_if_not_shortlisted'}),
}
DATASETS = {}
AUTHORITY_FIELDS = {
    ('events.HackathonProgrammeOptions', 'refund_on_withdrawal'): _DEF,
    ('events.HackathonProgrammeOptions', 'refund_if_not_shortlisted'): _DEF,
}
UNIQUE_CONSTRAINTS = ()
PURGE_ORDER = ()
