"""Presentation entries for release-2 lane L4 (membership lifecycle) audit actions.

Only ids, counts, field names, statuses and dates are shown: GSTIN, notes, imported
contact details, consent text and staff-written reasons never appear in audit meta.
"""

from django.utils.translation import gettext_noop
from .presentation_catalog_types import P

ENTRIES = (
    P("makerspace.financial_year_updated", gettext_noop("Financial year start month changed"), ("from_month", "to_month")),
    P("membership.plan_archived", gettext_noop("Membership plan archived"), ("plan_id",)),
    P("membership.plan_restored", gettext_noop("Membership plan restored"), ("plan_id",)),
    P("membership.term_status_changed", gettext_noop("Membership term standing changed"),
      ("membership_id", "term_id", "status", "event_id", "effective_at")),
    P("membership.extended", gettext_noop("Membership extended by staff"), ("membership_id", "term_id", "from", "to")),
    P("membership.renewal_reminder_sent", gettext_noop("Renewal reminder sent"), ("membership_id", "term_id", "day")),
    P("membership.record_updated", gettext_noop("Member record updated"), ("membership_id", "fields")),
    P("membership.title_created", gettext_noop("Member title created"), ("title_id", "fields")),
    P("membership.title_updated", gettext_noop("Member title updated"), ("title_id", "fields")),
    P("membership.title_archived", gettext_noop("Member title archived"), ("title_id",)),
    P("membership.title_restored", gettext_noop("Member title restored"), ("title_id",)),
    P("membership.title_assigned", gettext_noop("Member title assigned"), ("membership_id", "title_id", "primary")),
    P("membership.title_unassigned", gettext_noop("Member title removed"), ("membership_id", "title_id")),
    P("membership.consent_given", gettext_noop("Consent given"), ("membership_id", "consent_id", "purpose", "notice_version")),
    P("membership.consent_withdrawn", gettext_noop("Consent withdrawn"), ("membership_id", "consent_id", "purpose")),
    P("membership.erasure_requested", gettext_noop("Erasure requested"), ("membership_id", "request_id")),
    P("membership.erasure_withdrawn", gettext_noop("Erasure request withdrawn"), ("membership_id", "request_id")),
    P("membership.erasure_approved", gettext_noop("Erasure approved"), ("membership_id", "request_id")),
    P("membership.erasure_rejected", gettext_noop("Erasure rejected"), ("membership_id", "request_id")),
    P("membership.invite_link_created", gettext_noop("Membership invite link created"), ("link_id", "plan_id", "max_uses")),
    P("membership.invite_link_revoked", gettext_noop("Membership invite link revoked"), ("link_id", "uses")),
    P("membership.invite_link_redeemed", gettext_noop("Membership invite link used"), ("link_id", "uses")),
    P("membership.bulk_decided", gettext_noop("Join requests decided in bulk"), ("decision", "request_ids", "refused")),
    P("membership.imported", gettext_noop("Members imported"),
      ("batch_id", "created", "updated", "skipped", "invited", "record_only", "source")),
    P("membership.import_accepted", gettext_noop("Imported membership accepted"), ("membership_id", "imported_member_id", "term_id")),
    P("membership.summary_opted_out", gettext_noop("Opted out of the monthly membership summary"), ("user_id",)),
    P("membership.summary_opted_in", gettext_noop("Opted back in to the monthly membership summary"), ("user_id",)),
    # `payment.*` metadata is withheld by the dynamic deny policy, so the entry names the action only.
    P("payment.refund_case_term_ended", gettext_noop("Refund approval ended the membership term")),
)
