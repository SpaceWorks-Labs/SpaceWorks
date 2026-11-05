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
        "admin-member-card-photo",
    )},
    **{name: _DESIGN for name in (
        "admin-card-design", "admin-card-design-templates", "admin-card-design-publish", "admin-card-design-submit",
        "admin-card-design-approve", "admin-card-design-reject", "admin-card-design-reset", "admin-card-design-export",
        "admin-card-design-import", "admin-card-design-preview", "admin-card-design-assets",
        "admin-card-design-asset-finalize", "admin-card-design-asset", "admin-card-design-fonts",
        "admin-card-design-font-prepare", "admin-card-design-font-file",
    )},
    **{name: ("card_designs.CardJob", "makerspace_id") for name in (
        "admin-card-job", "admin-card-job-cancel", "admin-card-job-result",
    )},
    **{name: ("id_programmes.IdProgramme", "makerspace_id") for name in (
        "admin-id-programme", "admin-id-programme-design", "admin-id-programme-approval", "admin-id-programme-cards",
        "admin-id-programme-decide", "admin-id-programme-import-preview", "admin-id-programme-import",
        "admin-id-programme-card-jobs",
    )},
    **{name: ("id_programmes.IdProgrammeCard", "makerspace_id") for name in (
        "admin-id-programme-card", "admin-id-programme-card-download", "admin-id-programme-card-email",
        "admin-id-programme-card-photo-request", "admin-id-programme-card-photo",
    )},
    **{name: ("events.Event", "makerspace_id") for name in (
        "admin-event-card-designs", "admin-event-card-settings", "admin-event-id-cards", "admin-event-id-card-extras",
        "admin-event-card-jobs", "admin-event-card-scan",
    )},
    **{name: ("events.EventIdCard", "makerspace_id") for name in (
        "admin-event-id-card", "admin-event-id-card-revoke", "admin-event-id-card-download", "admin-event-id-card-photo",
    )},
}
