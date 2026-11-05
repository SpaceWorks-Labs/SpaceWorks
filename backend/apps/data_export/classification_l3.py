"""Release-2 lane L3 (ID cards): literal export classification (SPEC §13).

Exported with the space: card designs and their append-only revision and approval
history (tenant configuration), uploaded design artwork (private objects), the four
approval levels, the daily public-check counter (an aggregate, no PII), "photo needs
update" requests, member-card settings and the new member-card fields, ID programmes
with their holder cards and import runs, and event ID cards.

Omitted, deliberately:
* `CardVerifyToken`, `WalletPass`, `WalletDeviceRegistration` -- bearer credential
  material (a check link, a pass authentication digest, encrypted push tokens). They
  never appear in a report or an export; a moved space re-mints links on first use.
* `CardHolderExtras` -- the opt-in blood group and emergency contact (Q-I5): seen only
  by the holder and on the printed card, never in any export.
* `CardJob` -- operational job state; its result objects expire after 7 days.
* `CardFont` -- the deployment-wide font cache, not tenant data.
"""

from .types import TenantPredicate as P

EXPORTED_FIELDS = {
    "card_designs.CardDesign": "id makerspace domain name plan title programme organization event ticket_type status "
                               "document published_document published_revision published_at revision updated_by "
                               "created_at updated_at",
    "card_designs.CardDesignRevision": "id design revision document created_by created_at",
    "card_designs.CardDesignApproval": "id design revision requested_by decided_by decision note created_at decided_at",
    "card_designs.CardDesignAsset": "id asset_id makerspace kind object_key content_type size_bytes sha256 width_px "
                                    "height_px mean_colour ready uploaded_by created_at",
    "card_designs.CardApprovalSetting": "id makerspace group organization programme event required updated_at",
    "card_designs.CardVerifyCheckDay": "id makerspace day count",
    "card_designs.CardPhotoRequest": "id makerspace member_card programme_card event_card requested_by reason "
                                     "created_at reminded_at resolved_at",
    "makerspaces.MemberCardSettings": "id makerspace auto_issue email_on_issue public_verify verify_show_plan updated_at",
    "events.EventCardSettings": "id event extras_visible_to_organizers updated_at",
    "id_programmes.IdProgramme": "id organization makerspace name slug description status registration_open "
                                 "requires_approval id_prefix next_sequence validity_mode valid_until validity_days "
                                 "photo_mode form_schema public_verify email_daily_cap created_by created_at updated_at",
    "id_programmes.IdProgrammeCard": "id programme makerspace user name email email_digest answers photo_object_key "
                                     "photo_content_type photo_size_bytes photo_consent_at photo_consent_version status "
                                     "status_reason source invite_digest id_number sequence issued_at expires_at "
                                     "revoked_at last_emailed_at verify_show_name verify_show_photo verify_consent_at "
                                     "email_format created_at updated_at",
    "id_programmes.IdProgrammeImport": "id programme created_by created_at source_sha256 rows_total created skipped "
                                       "mapping",
    "events.EventIdCard": "id event makerspace registration person role printed_name photo_object_key "
                          "photo_content_type photo_size_bytes photo_consent_at photo_consent_version status revoked_at "
                          "revoked_reason revoked_by valid_until issued_at last_emailed_at verify_show_name "
                          "verify_show_photo verify_consent_at email_format updated_at",
}
FIELD_ADDITIONS = {
    "makerspaces.MemberCard": "revoked_note last_emailed_at verify_show_name verify_show_photo verify_consent_at "
                              "verify_consent_version email_format",
}
_CREDENTIAL = "Bearer credential material: never exported, reported or shown to staff (SPEC §13)."
OMITTED_MODELS = {
    "card_designs.CardVerifyToken": _CREDENTIAL,
    "card_designs.WalletPass": _CREDENTIAL,
    "card_designs.WalletDeviceRegistration": _CREDENTIAL,
    "card_designs.CardHolderExtras": "Opt-in blood group and emergency contact: the holder and the printed card only "
                                     "(Q-I5), never any export.",
    "card_designs.CardJob": "Operational job state; its private result objects expire 7 days after finishing.",
    "card_designs.CardFont": "Deployment-wide cache of open-licence font files; not tenant data.",
}
NON_CREDENTIAL = {
    ("id_programmes.IdProgrammeCard", "email_digest"): "Keyed HMAC of the holder email for one-entry-per-person; "
                                                       "it authenticates nothing.",
    ("id_programmes.IdProgrammeCard", "invite_digest"): "Digest of a spent or pending invite; the invite secret "
                                                        "itself is never stored.",
}
DATASET_SPECS = {
    "card_designs.CardDesign": ("cards/designs.csv", P(("makerspace",))),
    "card_designs.CardDesignRevision": ("cards/design_revisions.csv", P(("design__makerspace",))),
    "card_designs.CardDesignApproval": ("cards/design_approvals.csv", P(("design__makerspace",))),
    "card_designs.CardDesignAsset": ("cards/design_assets.csv", P(("makerspace",))),
    "card_designs.CardApprovalSetting": ("cards/approval_settings.csv", P(("makerspace",))),
    "card_designs.CardVerifyCheckDay": ("cards/verify_checks.csv", P(("makerspace",))),
    "card_designs.CardPhotoRequest": ("cards/photo_requests.csv", P(("makerspace",))),
    "makerspaces.MemberCardSettings": ("members/member_card_settings.csv", P(("makerspace",))),
    "id_programmes.IdProgramme": ("id_programmes/programmes.csv", P(("makerspace",))),
    "id_programmes.IdProgrammeCard": ("id_programmes/cards.csv", P(("makerspace",))),
    "id_programmes.IdProgrammeImport": ("id_programmes/imports.csv", P(("programme__makerspace",))),
    "events.EventIdCard": ("events/id_cards.csv", P(("makerspace",))),
    "events.EventCardSettings": ("events/card_settings.csv", P(("event__makerspace",))),
}
RELATIONAL_USER_FIELDS = frozenset({
    ("card_designs.CardDesign", "updated_by"),
    ("card_designs.CardDesignRevision", "created_by"),
    ("card_designs.CardDesignApproval", "requested_by"),
    ("card_designs.CardDesignApproval", "decided_by"),
    ("card_designs.CardDesignAsset", "uploaded_by"),
    ("card_designs.CardPhotoRequest", "requested_by"),
    ("card_designs.CardJob", "requested_by"),
    ("id_programmes.IdProgramme", "created_by"),
    ("id_programmes.IdProgrammeCard", "user"),
    ("id_programmes.IdProgrammeImport", "created_by"),
    ("events.EventIdCard", "person"),
    ("events.EventIdCard", "revoked_by"),
})
EXCLUDED_USER_EDGE_REASONS = {
    ("card_designs.CardJob", "requested_by"): "Requester of an omitted, expiring job.",
}
# Layout documents (no references), a forms schema and an import column mapping.
JSON_FIELDS = frozenset({
    ("card_designs.CardDesign", "document"),
    ("card_designs.CardDesign", "published_document"),
    ("card_designs.CardDesignRevision", "document"),
    ("id_programmes.IdProgramme", "form_schema"),
    ("id_programmes.IdProgrammeImport", "mapping"),
})


def extend(fields):
    fields.update(EXPORTED_FIELDS)
    for label, extra in FIELD_ADDITIONS.items():
        fields[label] += " " + extra
    return fields
