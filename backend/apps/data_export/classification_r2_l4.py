"""Release-2 lane L4 (membership lifecycle) export classification.

Imported by the `classification`, `datasets` and `references` barrels.

* New tenant rows that ARE the space's membership data and export with it: the term
  standing history, member records (GSTIN and staff notes are scoped PII), titles and
  their assignments, the consent ledger, erasure requests, import batches and imported
  (pending) members, and per-person summary opt-outs.
* `MembershipInviteLink` is a bearer credential (only a digest is stored): it is
  deployment-local and never travels; staff issue new links on the target.
* New columns on exported models (plans, terms, memberships, admission settings and
  the makerspace's financial-year month) are plain settings or frozen sale facts.
"""

from .types import TenantPredicate as P

EXPORTED_FIELDS = {
    "makerspaces.MembershipTermStatusEvent": "id makerspace membership term status effective_at recorded_at ends_at actor reason",
    "makerspaces.MembershipRecord": "id makerspace membership state_code gstin staff_notes updated_by updated_at",
    "makerspaces.MembershipTitle": "id makerspace name colour sort_order archived_at created_at updated_at",
    "makerspaces.MembershipTitleAssignment": "id makerspace membership title is_primary assigned_by created_at",
    "makerspaces.MembershipConsent": "id makerspace membership purpose notice_version source given_at withdrawn_at",
    "makerspaces.MembershipErasureRequest": "id makerspace membership status member_note decision_note decided_by created_at updated_at decided_at",
    "makerspaces.MembershipImportBatch": "id makerspace file_name file_kind counts created_by created_at",
    "makerspaces.ImportedMember": "id makerspace batch status name email phone external_number plan starts_on ends_on state_code gstin staff_notes invitation membership created_by created_at updated_at accepted_at",
    "makerspaces.MembershipSummaryOptOut": "id makerspace user created_at",
}

FIELD_ADDITIONS = {
    "makerspaces.Makerspace": "financial_year_start_month",
    "makerspaces.MembershipPlan": "plan_type fixed_end_date renewal_amount joining_fee rejoin_rule rejoin_after_days "
                                  "payment_timing join_mode application_schema late_renewal slug description sort_order "
                                  "is_public archived_at",
    "makerspaces.MembershipTerm": "kind price joining_fee currency plan_type admission_request",
    "makerspaces.MakerspaceMembership": "member_number source",
    "makerspaces.MakerspaceMembershipSettings": "rejoin_after_days member_number_pattern privacy_notice_version consent_purposes",
}

OMITTED_MODELS = {
    "makerspaces.MembershipInviteLink": "Bearer invite credential (digest only); staff issue new links on the target.",
}

DATASET_SPECS = {
    "makerspaces.MembershipTermStatusEvent": ("members/term_history.csv", P(("makerspace",))),
    "makerspaces.MembershipRecord": ("members/records.csv", P(("makerspace",))),
    "makerspaces.MembershipTitle": ("members/titles.csv", P(("makerspace",))),
    "makerspaces.MembershipTitleAssignment": ("members/title_assignments.csv", P(("makerspace",))),
    "makerspaces.MembershipConsent": ("members/consents.csv", P(("makerspace",))),
    "makerspaces.MembershipErasureRequest": ("members/erasure_requests.csv", P(("makerspace",))),
    "makerspaces.MembershipImportBatch": ("members/import_batches.csv", P(("makerspace",))),
    "makerspaces.ImportedMember": ("members/imported_members.csv", P(("makerspace",))),
    "makerspaces.MembershipSummaryOptOut": ("members/summary_opt_outs.csv", P(("makerspace",))),
}

RELATIONAL_USER_FIELDS = frozenset({
    ("makerspaces.MembershipTermStatusEvent", "actor"),
    ("makerspaces.MembershipRecord", "updated_by"),
    ("makerspaces.MembershipTitleAssignment", "assigned_by"),
    ("makerspaces.MembershipErasureRequest", "decided_by"),
    ("makerspaces.MembershipImportBatch", "created_by"),
    ("makerspaces.ImportedMember", "created_by"),
    ("makerspaces.MembershipSummaryOptOut", "user"),
    ("makerspaces.MembershipInviteLink", "created_by"),
})

# JSON columns with no embedded model references: consent purpose keys/labels, import
# counts, and a plan's own application form (the same schema shape as the space form).
NON_REFERENCE_JSON_FIELDS = frozenset({
    ("makerspaces.MakerspaceMembershipSettings", "consent_purposes"),
    ("makerspaces.MembershipImportBatch", "counts"),
    ("makerspaces.MembershipPlan", "application_schema"),
})

# The credential-name guard matches `*state`; a two-digit Indian state code is not one.
NON_CREDENTIAL = {
    ("makerspaces.MembershipRecord", "state_code"): "Two-digit GST state code for the place of supply, not a secret.",
    ("makerspaces.ImportedMember", "state_code"): "Two-digit GST state code from the import file, not a secret.",
}
