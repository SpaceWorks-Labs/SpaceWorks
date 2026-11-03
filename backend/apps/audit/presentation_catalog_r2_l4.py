"""Presentation entries for release-2 lane L4 (membership lifecycle) audit actions.

Only ids, counts, field names, statuses and dates are shown: GSTIN, notes, imported
contact details, consent text and staff-written reasons never appear in audit meta.
"""

from .presentation_catalog_types import P

ENTRIES = (
    P("makerspace.financial_year_updated", "Financial year start month changed", ("from_month", "to_month")),
    P("membership.plan_archived", "Membership plan archived", ("plan_id",)),
    P("membership.plan_restored", "Membership plan restored", ("plan_id",)),
    P("membership.term_status_changed", "Membership term standing changed",
      ("membership_id", "term_id", "status", "event_id", "effective_at")),
    P("membership.extended", "Membership extended by staff", ("membership_id", "term_id", "from", "to")),
    P("membership.renewal_reminder_sent", "Renewal reminder sent", ("membership_id", "term_id", "day")),
    P("membership.record_updated", "Member record updated", ("membership_id", "fields")),
    P("membership.title_created", "Member title created", ("title_id", "fields")),
    P("membership.title_updated", "Member title updated", ("title_id", "fields")),
    P("membership.title_archived", "Member title archived", ("title_id",)),
    P("membership.title_restored", "Member title restored", ("title_id",)),
    P("membership.title_assigned", "Member title assigned", ("membership_id", "title_id", "primary")),
    P("membership.title_unassigned", "Member title removed", ("membership_id", "title_id")),
    P("membership.consent_given", "Consent given", ("membership_id", "consent_id", "purpose", "notice_version")),
    P("membership.consent_withdrawn", "Consent withdrawn", ("membership_id", "consent_id", "purpose")),
    P("membership.erasure_requested", "Erasure requested", ("membership_id", "request_id")),
    P("membership.erasure_withdrawn", "Erasure request withdrawn", ("membership_id", "request_id")),
    P("membership.erasure_approved", "Erasure approved", ("membership_id", "request_id")),
    P("membership.erasure_rejected", "Erasure rejected", ("membership_id", "request_id")),
    P("membership.invite_link_created", "Membership invite link created", ("link_id", "plan_id", "max_uses")),
    P("membership.invite_link_revoked", "Membership invite link revoked", ("link_id", "uses")),
    P("membership.invite_link_redeemed", "Membership invite link used", ("link_id", "uses")),
    P("membership.bulk_decided", "Join requests decided in bulk", ("decision", "request_ids", "refused")),
    P("membership.imported", "Members imported",
      ("batch_id", "created", "updated", "skipped", "invited", "record_only", "source")),
    P("membership.import_accepted", "Imported membership accepted", ("membership_id", "imported_member_id", "term_id")),
    P("membership.summary_opted_out", "Opted out of the monthly membership summary", ("user_id",)),
    P("membership.summary_opted_in", "Opted back in to the monthly membership summary", ("user_id",)),
    # `payment.*` metadata is withheld by the dynamic deny policy, so the entry names the action only.
    P("payment.refund_case_term_ended", "Refund approval ended the membership term"),
)
