"""Account-merge dispositions for lane L18 (donations, pledges, sponsors and calendar links)."""

from .merge_registry_types import KEEP_ON_SHELL as K, REPOINT as R, UNIQUE_RESOLVE as U

_MUTABLE = "Mutable ownership or attribution; moves to the survivor."
_MONEY = ("Who gave the money. Stays with the account that gave, exactly like Payment.member, which "
          "validates against it (actor_ids_for follows the alias).")
_HISTORY = "Attribution of who recorded or decided something; stays with the account that acted."

ROWS = (
    (K, "payments.Donation", "donor created_by", _MONEY),
    (R, "payments.DonationPledge", "donor", "A live promise to give; the survivor keeps paying it."),
    (K, "payments.DonationPledge", "created_by", _HISTORY),
    (R, "payments.DonationCampaign", "created_by", _MUTABLE),
    (R, "payments.DonationSettings", "updated_by", _MUTABLE),
    (R, "payments.Sponsor", "created_by", _MUTABLE),
    (R, "payments.SponsorEventLink", "created_by", _MUTABLE),
    (K, "payments.SponsorPerk", "fulfilled_by", _HISTORY),
    (K, "payments.SponsorshipCharge", "created_by", _HISTORY),
    (U, "events.PersonalCalendarFeed", "user",
     "One link per person, space and kind; survivor wins, the loser stays revoked on the shell."),
)
