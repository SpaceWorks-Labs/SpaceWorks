"""Release-2 lane L3 (ID cards): tenant-dump field snapshot and authority (SPEC §13).

Designs, programmes, programme and event cards travel with the space (data_export
`classification_l3`). Holder identity on programme and event cards behaves like the
member card's: it travels for full users and is dropped for stub-linked ones. Invite
digests are reset (an invite never crosses servers) and email digests are reset and
rebuilt on the target (`manage.py rebuild_programme_email_digests`), because they are
keyed with the source deployment's secret. Verify tokens, wallet passes, sensitive
extras, jobs and the font cache never travel (omitted models).
"""

FIELD_NAMES = {
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
    "card_designs.CardJob": "id makerspace kind scope scope_id requested_by params targets idempotency_key total done "
                            "failed attempts state error_code parts result_key result_size result_content_type "
                            "result_expires_at lease_until created_at started_at finished_at",
    "card_designs.CardFont": "id family weight state font_key sha256 size_bytes error requested_at fetched_at",
    "card_designs.CardVerifyToken": "id makerspace member_card programme_card event_card token created_at retired_at "
                                    "retired_reason",
    "card_designs.CardHolderExtras": "id makerspace member_card programme_card event_card blood_group "
                                     "emergency_contact_name emergency_contact_phone consent_at consent_version updated_at",
    "card_designs.WalletPass": "id makerspace member_card programme_card event_card platform serial auth_token_digest "
                               "pass_type_id generation content_digest created_at last_updated_at voided_at",
    "card_designs.WalletDeviceRegistration": "id wallet_pass device_digest push_token created_at",
    "makerspaces.MemberCardSettings": "id makerspace auto_issue email_on_issue public_verify verify_show_plan updated_at",
    "events.EventCardSettings": "id event extras_visible_to_organizers updated_at",
    "id_programmes.IdProgramme": "id organization makerspace name slug description status registration_open "
                                 "requires_approval id_prefix next_sequence validity_mode valid_until validity_days "
                                 "photo_mode form_schema public_verify email_daily_cap created_by created_at updated_at",
    "id_programmes.IdProgrammeCard": "id programme makerspace user name email email_digest answers photo_object_key "
                                     "photo_content_type photo_size_bytes photo_consent_at photo_consent_version status "
                                     "status_reason source invite_digest id_number sequence issued_at expires_at "
                                     "revoked_at last_emailed_at verify_show_name verify_show_photo verify_consent_at "
                                     "created_at updated_at",
    "id_programmes.IdProgrammeImport": "id programme created_by created_at source_sha256 rows_total created skipped "
                                       "mapping",
    "events.EventIdCard": "id event makerspace registration person role printed_name photo_object_key "
                          "photo_content_type photo_size_bytes photo_consent_at photo_consent_version status revoked_at "
                          "revoked_reason revoked_by valid_until issued_at last_emailed_at verify_show_name "
                          "verify_show_photo verify_consent_at updated_at",
}
FIELD_NAMES = {label: frozenset(names.split()) for label, names in FIELD_NAMES.items()}
MEMBER_CARD_FIELDS = "revoked_note last_emailed_at verify_show_name verify_show_photo verify_consent_at verify_consent_version"
EXTRA_FIELDS = {"makerspaces.MemberCard": frozenset(MEMBER_CARD_FIELDS.split())}
_OMITTED = {"card_designs.CardJob", "card_designs.CardFont", "card_designs.CardVerifyToken",
            "card_designs.CardHolderExtras", "card_designs.WalletPass", "card_designs.WalletDeviceRegistration"}
PROJECTED_LABELS = frozenset(label for label in FIELD_NAMES if label not in _OMITTED)
_PHOTO = "photo_object_key photo_content_type photo_size_bytes photo_consent_at photo_consent_version"


def authority_entries(authority, disposition):
    def same(label, names, chosen, reason):
        return tuple(((label, name), authority(chosen, reason)) for name in names.split())

    keep, holder = disposition.PRESERVE, (disposition.PRESERVE, disposition.DROP)
    return (
        *same("makerspaces.MemberCard", MEMBER_CARD_FIELDS, keep,
              "Card opt-ins, the revocation note and the email stamp are the card's own record."),
        *same("id_programmes.IdProgrammeCard", f"name email answers status_reason {_PHOTO}", holder,
              "Full-user holder identity travels; stub-linked identity content does not."),
        *same("id_programmes.IdProgrammeCard", "invite_digest email_digest", disposition.RESET,
              "Invite and email digests are keyed with the source deployment's secret; the target rebuilds them."),
        *same("events.EventIdCard", f"printed_name revoked_reason {_PHOTO}", holder,
              "Full-user holder identity travels; stub-linked identity content does not."),
    )
