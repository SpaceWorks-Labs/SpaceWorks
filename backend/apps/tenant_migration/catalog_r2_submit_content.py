"""Release-2 lane r2-submit-content (submission stages, shortlist gates, extensions) dispositions.

Imported by the programme catalogue files with one explicit line each, like L21b's rows, so the
programme guards (field snapshot, dataset, authority, uniqueness, purge, JSON surfaces) see these
rows exactly like the other submission rows. User edges (`created_by`, `published_by`) are
classified in `accounts/merge_registry_rows_submit_content.py`.
"""

FIELD_NAMES = {
    'events.SubmissionStage': frozenset(
        'id event position name description opens_at deadline grace_minutes late_policy resubmission '
        'requires_previous content_mode required_link_kinds min_files max_files max_links accepted_families '
        'max_bytes_per_file video_hosts custom_fields shortlist_after shortlist_label public_after_publish version '
        'created_at updated_at'.split()),
    'events.SubmissionStageEntry': frozenset('id submission stage current_snapshot submitted_at triage version'.split()),
    'events.StageExtension': frozenset('id stage team until reason created_by created_at'.split()),
    'events.SnapshotStage': frozenset('id snapshot stage extension'.split()),
    'events.StageShortlist': frozenset(
        'id event stage source_round selection top_n fingerprint created_by created_at amends'.split()),
    'events.StageShortlistEntry': frozenset('id shortlist submission snapshot source_rank'.split()),
    'events.StageShortlistAnnouncement': frozenset('id event shortlist published_at published_by'.split()),
}
#: New columns on existing programme models.
EXTRA_FIELDS = {
    'events.JudgingRound': frozenset({'submission_stage', 'share_feedback', 'judge_reminders'}),
    'events.JudgeScore': frozenset({'team_feedback'}),
    'events.HackathonProgrammeOptions': frozenset({'stage_reminder_email', 'shortlist_email', 'entry_fee_stage'}),
}

DATASETS = {
    'events.SubmissionStage': ('events/programme/SubmissionStage.csv', 'event__makerspace'),
    'events.SubmissionStageEntry': ('events/programme/SubmissionStageEntry.csv', 'submission__event__makerspace'),
    'events.StageExtension': ('events/programme/StageExtension.csv', 'stage__event__makerspace'),
    'events.SnapshotStage': ('events/programme/SnapshotStage.csv', 'stage__event__makerspace'),
    'events.StageShortlist': ('events/programme/StageShortlist.csv', 'event__makerspace'),
    'events.StageShortlistEntry': ('events/programme/StageShortlistEntry.csv', 'shortlist__event__makerspace'),
    'events.StageShortlistAnnouncement': ('events/programme/StageShortlistAnnouncement.csv', 'event__makerspace'),
}

JSON_FIELDS = frozenset({
    ('events.SubmissionStage', 'required_link_kinds'),
    ('events.SubmissionStage', 'accepted_families'),
    ('events.SubmissionStage', 'video_hosts'),
    ('events.SubmissionStage', 'custom_fields'),
})

_DEF = 'Authored stage or event configuration; it travels as data and grants no target authority.'
_EVIDENCE = 'Append-only selection, extension or workflow evidence; preserved, remapped, never a grant of target authority.'
_REFERENCE = 'Typed subject/attribution reference; remapped retained history alone grants no target authority.'
_GATE = 'Programme disclosure input; imported triage and selections are rechecked by live target authority.'

_STAGE_DEF = ('position', 'name', 'description', 'opens_at', 'deadline', 'grace_minutes', 'late_policy', 'resubmission',
              'requires_previous', 'content_mode', 'required_link_kinds', 'min_files', 'max_files', 'max_links',
              'accepted_families', 'max_bytes_per_file', 'video_hosts', 'custom_fields', 'shortlist_after',
              'shortlist_label', 'public_after_publish', 'version', 'created_at', 'updated_at')

AUTHORITY_FIELDS = {
    ('events.JudgingRound', 'submission_stage'): _REFERENCE,
    ('events.JudgingRound', 'share_feedback'): _DEF, ('events.JudgingRound', 'judge_reminders'): _DEF,
    ('events.JudgeScore', 'team_feedback'): ('Private historical evidence; disclosure stays owner/permission scoped and '
                                             'sensitive sources stay encrypted.'),
    **{('events.HackathonProgrammeOptions', name): _DEF for name in (
        'stage_reminder_email', 'shortlist_email', 'entry_fee_stage')},
    **{('events.SubmissionStage', name): _DEF for name in _STAGE_DEF},
    ('events.SubmissionStage', 'event'): _REFERENCE,
    **{('events.SubmissionStageEntry', name): _EVIDENCE for name in ('submitted_at', 'version')},
    ('events.SubmissionStageEntry', 'triage'): _GATE,
    **{('events.SubmissionStageEntry', name): _REFERENCE for name in ('submission', 'stage', 'current_snapshot')},
    **{('events.StageExtension', name): _EVIDENCE for name in ('until', 'reason', 'created_at')},
    **{('events.StageExtension', name): _REFERENCE for name in ('stage', 'team', 'created_by')},
    **{('events.SnapshotStage', name): _REFERENCE for name in ('snapshot', 'stage', 'extension')},
    **{('events.StageShortlist', name): _EVIDENCE for name in ('selection', 'top_n', 'fingerprint', 'created_at')},
    **{('events.StageShortlist', name): _REFERENCE for name in ('event', 'stage', 'source_round', 'created_by', 'amends')},
    ('events.StageShortlistEntry', 'source_rank'): _EVIDENCE,
    **{('events.StageShortlistEntry', name): _REFERENCE for name in ('shortlist', 'submission', 'snapshot')},
    ('events.StageShortlistAnnouncement', 'published_at'): _EVIDENCE,
    **{('events.StageShortlistAnnouncement', name): _REFERENCE for name in ('event', 'shortlist', 'published_by')},
}

# The stage-position, stage-entry and shortlist-entry constraints include their tenant-owned parent
# column (event, submission, shortlist) and carry no deployment-global risk, so only the two
# OneToOne scopes are registered.
UNIQUE_CONSTRAINTS = (
    ('events.SnapshotStage', 'field:snapshot'),
    ('events.StageShortlistAnnouncement', 'field:shortlist'),
)

# Children first: announcements, shortlist entries, shortlists, snapshot-stage records, entries and
# extensions all precede their SubmissionStage parent, which precedes nothing else here.
PURGE_ORDER = (
    ('events.StageShortlistAnnouncement', 'event__makerspace'),
    ('events.StageShortlistEntry', 'shortlist__event__makerspace'),
    ('events.StageShortlist', 'event__makerspace'),
    ('events.SnapshotStage', 'stage__event__makerspace'),
    ('events.SubmissionStageEntry', 'submission__event__makerspace'),
    ('events.StageExtension', 'stage__event__makerspace'),
)
#: SubmissionStage is purged after the judging rounds that point at it (PROTECT).
STAGE_PURGE = (('events.SubmissionStage', 'event__makerspace'),)

#: G11 (#180): reimbursement columns, registered in the first-party field snapshot like L21a's
#: ``min_application_stage`` (this is not a programme-catalogue model).
REIMBURSEMENT_EXTRA_FIELDS = {
    'event_reimbursements.ReimbursementProgramme': frozenset({'required_submission', 'required_submission_stage'}),
    # S14: the stage-deadline push signal on L2's (dropped) integrity job row.
    'events.SubmissionIntegrityCheck': frozenset({'after_deadline_state'}),
}
