"""Lane L21b rows in the capture-bound money fingerprint.

A prize payout records money the space paid out (with its reversal rows), and the per-event options
hold the entry and team fees a later charge is raised at. Entry-fee and team charges themselves are
ordinary `Payment` rows, already covered. Each key is omitted when empty, so a space that never paid
a prize or set a fee keeps its existing fingerprint.
"""

from .money_digest_r2_l6 import _rows


def l21b_money_rows(makerspace_id, using="default"):
    from django.apps import apps

    get = apps.get_model
    fees = [row for row in _rows(get("events.HackathonProgrammeOptions"), using,
                                 ("id", "event_id", "entry_fee", "team_fee", "refund_on_disqualification"),
                                 event__makerspace_id=makerspace_id)
            if row["entry_fee"] != "None" or row["team_fee"] != "None"]
    parts = {
        "event_prize_payouts": _rows(get("events.HackathonPrizePayout"), using,
                                     ("id", "award_id", "kind", "reverses_id", "amount", "currency", "ledger_entry_id"),
                                     makerspace_id=makerspace_id),
        "event_programme_fees": fees,
    }
    return {key: rows for key, rows in parts.items() if rows}
