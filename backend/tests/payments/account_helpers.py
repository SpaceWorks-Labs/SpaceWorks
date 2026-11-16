"""Member payers are separate principals from the staff who manage their charges."""

from tests.return_helpers import make_member


def make_payer(username, makerspace):
    return make_member(username, makerspace, membership_role="member", role="requester")
