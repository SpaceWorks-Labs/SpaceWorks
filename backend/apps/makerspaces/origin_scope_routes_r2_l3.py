"""Origin-scope table for release 2 L3's staff routes that name only a row.

Card designs, card jobs and member cards carry their own space; a verified custom staff
origin pins them to it. The three pre-existing member-card routes (reissue, revoke,
print) had no lookup and are added here too.
"""

_CARD = ("makerspaces.MemberCard", "makerspace_id")
_DESIGN = ("card_designs.CardDesign", "makerspace_id")

MODEL_LOOKUPS = {
    **{name: _CARD for name in (
        "admin-member-card-reissue", "admin-member-card-revoke", "admin-member-card-print",
        "admin-member-card-download", "admin-member-card-email", "admin-member-card-photo-request",
        "admin-member-card-photo", "admin-member-card-print-face",
    )},
    **{name: ("card_designs.StaffCard", "makerspace_id") for name in (  # O-B4 part 2: staff ID cards
        "admin-staff-card", "admin-staff-card-reissue", "admin-staff-card-revoke", "admin-staff-card-print-face",
        "admin-staff-card-download",
    )},
    **{name: _DESIGN for name in (
        "admin-card-design", "admin-card-design-templates", "admin-card-design-publish", "admin-card-design-submit",
        "admin-card-design-approve", "admin-card-design-reject", "admin-card-design-reset", "admin-card-design-export",
        "admin-card-design-import", "admin-card-design-preview", "admin-card-design-assets",
        "admin-card-design-asset-finalize", "admin-card-design-asset", "admin-card-design-fonts",
        "admin-card-design-font-prepare", "admin-card-design-font-file", "admin-card-design-revisions",
        "admin-card-design-revision", "admin-card-design-restore", "admin-card-design-holders",
        "admin-card-design-calibration", "admin-card-design-archive", "admin-card-design-unarchive",
        "admin-card-design-badge-export", "admin-card-design-badge-import", "admin-card-design-badge-convert",
    )},
    **{name: ("card_designs.CardJob", "makerspace_id") for name in (
        "admin-card-job", "admin-card-job-cancel", "admin-card-job-result",
    )},
    **{name: ("id_programmes.IdProgramme", "makerspace_id") for name in (
        "admin-id-programme", "admin-id-programme-design", "admin-id-programme-approval", "admin-id-programme-cards",
        "admin-id-programme-decide", "admin-id-programme-import-preview", "admin-id-programme-import",
        "admin-id-programme-card-jobs", "admin-id-programme-card-job-preview", "admin-id-programme-archive",
        "admin-id-programme-unarchive",
    )},
    **{name: ("id_programmes.IdProgrammeCard", "makerspace_id") for name in (
        "admin-id-programme-card", "admin-id-programme-card-download", "admin-id-programme-card-email",
        "admin-id-programme-card-photo-request", "admin-id-programme-card-photo",
    )},
    **{name: ("events.Event", "makerspace_id") for name in (
        "admin-event-card-designs", "admin-event-card-settings", "admin-event-id-cards", "admin-event-id-card-extras",
        "admin-event-card-jobs", "admin-event-card-scan", "admin-event-card-job-preview",
        "admin-event-badge-designs", "admin-event-badge-design-role",
        "admin-event-badge-desk", "admin-event-badge-print-receipts",
    )},
    **{name: ("events.EventIdCard", "makerspace_id") for name in (
        "admin-event-id-card", "admin-event-id-card-revoke", "admin-event-id-card-download", "admin-event-id-card-photo",
    )},
}
