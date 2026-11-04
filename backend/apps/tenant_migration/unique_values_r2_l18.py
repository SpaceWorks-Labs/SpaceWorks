"""Deployment-global uniqueness for lane L18's rows (donations, pledges, sponsors).

An event-sponsor link and per-parent unique rows follow their remapped parent (per-space
unique rows carry the remapped space and are no deployment-global risk). A guest's link secret is bearer material: the target mints a fresh one.
"""

from .unique_values_policy import FRESH, REMAP, _policy

_FOLLOW = "Unique per remapped parent row; follows the imported parent."
_SECRET = "A guest's link secret is replaced on the target; guests get fresh links."

RULES = {
    ("payments.Donation", "donation_one_per_pledge_period"): _policy(REMAP, _FOLLOW),
    ("payments.Donation", "field:access_secret"): _policy(FRESH, _SECRET),
    ("payments.DonationPledge", "field:manage_secret"): _policy(FRESH, _SECRET),
    ("payments.SponsorPerk", "sponsor_perk_copied_once"): _policy(REMAP, _FOLLOW),
    ("payments.SponsorEventLink", "field:event_sponsor"): _policy(REMAP, _FOLLOW),
}
