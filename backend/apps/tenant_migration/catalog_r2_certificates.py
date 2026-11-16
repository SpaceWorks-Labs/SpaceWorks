"""Lane r2-idcards-best (#199) dispositions: certificate signatories and their design approvals.

Imported by the programme catalogue files with one explicit line each, as People's choice is, so
the programme guards (field snapshot, dataset, authority, uniqueness, purge) see these rows like
the other certificate rows. User edges (`member`, `approved_by`) are classified in
`accounts/merge_registry_rows_certificates.py`.
"""

FIELD_NAMES = {
    'events.EventCertificateSignatory': frozenset(
        'id event slot name title member signature version created_at updated_at'.split()),
    'events.EventCertificateSignatoryApproval': frozenset(
        'id signatory template_revision signatory_version approved_by approved_at'.split()),
}
#: New columns on existing programme models.
EXTRA_FIELDS = {
    'events.EventCertificatePublicationPolicy': frozenset({'signatory_approval_required'}),
}

DATASETS = {
    'events.EventCertificateSignatory': ('events/programme/EventCertificateSignatory.csv', 'event__makerspace'),
    'events.EventCertificateSignatoryApproval': ('events/programme/EventCertificateSignatoryApproval.csv',
                                                 'signatory__event__makerspace'),
}

#: Account edges exported as personal references (the signatory account, the approver).
USER_FIELDS = frozenset({('events.EventCertificateSignatory', 'member'),
                         ('events.EventCertificateSignatoryApproval', 'approved_by')})

_DEF = 'Authored certificate configuration; it travels as data and grants no target authority.'
_EVIDENCE = 'Append-only approval evidence; preserved, remapped, and never a grant of target authority.'
_REFERENCE = 'Typed subject/attribution reference; remapped retained history alone grants no target authority.'

AUTHORITY_FIELDS = {
    **{('events.EventCertificateSignatory', name): _DEF for name in (
        'slot', 'name', 'title', 'version', 'created_at', 'updated_at')},
    **{('events.EventCertificateSignatory', name): _REFERENCE for name in ('event', 'member', 'signature')},
    **{('events.EventCertificateSignatoryApproval', name): _EVIDENCE for name in (
        'signatory_version', 'approved_at')},
    **{('events.EventCertificateSignatoryApproval', name): _REFERENCE for name in (
        'signatory', 'template_revision', 'approved_by')},
    ('events.EventAttendanceCertificate', 'holder_name_public'): (
        'Holder disclosure choice; imported certificates reset to private and the holder chooses again.'),
    ('events.EventCertificatePublicationPolicy', 'signatory_approval_required'): (
        'Programme authority/disclosure input; imported live grants, selections and publication are reset '
        'and runtime policy rechecks the target.'),
}

# Every unique key includes the row's tenant root (event, or the signatory of one event).
UNIQUE_CONSTRAINTS = ()

# Children first: approvals precede the signatories they name; signatories precede the artwork
# (PROTECT) and template revisions they point at.
PURGE_ORDER = (
    ('events.EventCertificateSignatoryApproval', 'signatory__event__makerspace'),
    ('events.EventCertificateSignatory', 'event__makerspace'),
)
