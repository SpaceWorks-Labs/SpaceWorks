"""Choice vocabularies shared by membership plans, the space admission policy and terms.

Kept in one module so a plan override and the space default it overrides can never
drift into two spellings of the same rule.
"""
from django.db import models


class PlanType(models.TextChoices):
    #: A term lasts the plan interval (monthly / yearly / custom days) -- the shipped behaviour.
    ROLLING = "rolling", "Rolling"
    #: A term ends when the space's financial year ends (`makerspaces.financial_year`).
    FINANCIAL_YEAR = "financial_year", "Financial year"
    #: Every term ends on the plan's `fixed_end_date`.
    FIXED_END = "fixed_end", "Fixed end date"
    #: A term never ends and never renews.
    LIFETIME = "lifetime", "Lifetime"


class JoinMode(models.TextChoices):
    OPEN = "open", "Open"
    APPROVAL = "approval", "Approval"
    INVITE_ONLY = "invite_only", "Invite only"
    VOUCH = "vouch", "Vouch"
    CLOSED = "closed", "Closed"


class PaymentTiming(models.TextChoices):
    AFTER = "after_activation", "Activate then charge"
    BEFORE = "before_activation", "Pay before activation"


class RejoinRule(models.TextChoices):
    """When a joining fee is charged.

    * never -- no joining fee at all (a plan override waiving the space's fee);
    * once -- on the first join only (the shipped default);
    * each_join -- on every join, rejoins included;
    * after_lapse -- on the first join, and again on a rejoin after more than
      `rejoin_after_days` days without a membership.
    """
    NEVER = "never", "No joining fee"
    ONCE = "once", "Joining dues once"
    EACH_JOIN = "each_join", "Joining dues on each join"
    AFTER_LAPSE = "after_lapse", "Joining dues again after a lapse"


class LateRenewal(models.TextChoices):
    """Where a renewal opened after the old term ended (inside its grace) starts."""
    BACKDATE = "backdate", "Backdate to the old end"
    PAYMENT_DAY = "payment_day", "Start on the renewal day"


class TermKind(models.TextChoices):
    NEW = "new", "New"
    RENEWAL = "renewal", "Renewal"
    REINSTATEMENT = "reinstatement", "Reinstatement"


class TermStanding(models.TextChoices):
    """The standing a term is in, as recorded in its append-only history.

    The stored `MembershipTerm.status` keeps its three shipped values (active /
    expired / cancelled) so every reader of it keeps working; upcoming, grace, ended
    and lapsed are derived from it and the dates, and recorded here when they happen.
    """
    UPCOMING = "upcoming", "Upcoming"
    ACTIVE = "active", "Active"
    GRACE = "grace", "In grace"
    ENDED = "ended", "Ended"
    LAPSED = "lapsed", "Lapsed"
    CANCELLED = "cancelled", "Cancelled"
    EXTENDED = "extended", "Extended"


class MemberSource(models.TextChoices):
    JOIN = "join", "Joined"
    MANUAL = "manual", "Added by staff"
    IMPORT = "import", "Imported"


#: Display-only title colours: the brand accent presets (never tenant hex values).
TITLE_COLOURS = (
    ("", "Neutral"),
    ("maker_teal", "Maker Teal"),
    ("workshop_orange", "Workshop Orange"),
    ("citron", "Citron"),
    ("sky_blue", "Sky Blue"),
    ("warm_yellow", "Warm Yellow"),
)
