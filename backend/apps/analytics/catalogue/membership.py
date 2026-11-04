"""Analytics views: members, membership plans and membership terms.

`members` is the ONLY view that carries personal data: a display name and an email, both
NULL unless the space turned "Show member details" on (always NULL on the platform). It is a
lookup view because the people a space knows are platform account rows (`accounts.User`),
which the fixed-role policy hides; its explicit filter lists only people with a membership
in the login's own space. Every other view names a person by `member_id` alone.
"""

from .types import Col, View

D = "membership"
_NAME = ("coalesce(nullif(u.display_name, ''), "
         "nullif(trim(concat_ws(' ', u.first_name, u.last_name)), ''))")

VIEWS = (
    View("members", D, "Everyone with a membership in the space, staff and community.",
         "FROM {makerspaces.MakerspaceMembership} m JOIN {accounts.User} u ON u.id = m.user_id",
         "m.makerspace_id", (
             Col("member_id", "m.user_id", "Person id; the member_id of every other view."),
             Col("membership_id", "m.id", "Membership id."),
             Col("member_number", "m.member_number", "Member number."),
             Col("track", "m.track", "Community member or staff."),
             Col("status", "m.status", "Membership state."),
             Col("source", "m.source", "How they joined."),
             Col("created_at", "m.created_at", "Joined."),
             Col("activated_at", "m.activated_at", "Activated."),
             Col("revoked_at", "m.revoked_at", "Revoked."),
             Col("verified", "m.verified_at IS NOT NULL", "Verified by staff."),
             Col("waiver_accepted", "m.waiver_accepted_at IS NOT NULL", "Signed the waiver."),
             Col("display_name", _NAME, "Name (masked unless the space shows member details).", pii=True),
             Col("email", "u.email", "Email (masked unless the space shows member details).", pii=True),
         ), lookup=True),
    View("membership_plans", D, "Membership plans and their prices.",
         "FROM {makerspaces.MembershipPlan} p", "p.makerspace_id", (
             Col("plan_id", "p.id", "Plan id."),
             Col("name", "p.name", "Plan name."),
             Col("plan_type", "p.plan_type", "Plan type."),
             Col("interval", "p.interval", "Billing interval."),
             Col("amount", "p.amount", "Price per term."),
             Col("joining_fee", "p.joining_fee", "Joining fee."),
             Col("currency", "p.currency", "Currency."),
             Col("is_active", "p.is_active", "Offered."),
             Col("is_public", "p.is_public", "Shown publicly."),
             Col("created_at", "p.created_at", "Created."),
         )),
    View("membership_terms", D, "Membership terms: who held which plan, when and for how much.",
         "FROM {makerspaces.MembershipTerm} t "
         "JOIN {makerspaces.MakerspaceMembership} m ON m.id = t.membership_id", "m.makerspace_id", (
             Col("term_id", "t.id", "Term id."),
             Col("membership_id", "t.membership_id", "Membership (members)."),
             Col("member_id", "m.user_id", "Member (members)."),
             Col("plan_id", "t.plan_id", "Plan (membership_plans)."),
             Col("kind", "t.kind", "New, renewal and so on."),
             Col("status", "t.status", "Term state."),
             Col("starts_at", "t.starts_at", "Starts."),
             Col("ends_at", "t.ends_at", "Ends."),
             Col("price", "t.price", "Frozen price."),
             Col("joining_fee", "t.joining_fee", "Frozen joining fee."),
             Col("currency", "t.currency", "Currency."),
             Col("created_at", "t.created_at", "Created."),
         )),
)
