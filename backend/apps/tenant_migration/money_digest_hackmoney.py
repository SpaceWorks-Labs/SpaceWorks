"""Hack-money rows in the capture-bound money fingerprint.

A prize share is money a winner is owed; an outcome may carry a recovered amount and its ledger
receipt; the event money settings decide the tax a payout proposes; a deposit amount decides
what a confirmed place is charged. Each key is omitted when
empty, so a space that never used them keeps its existing fingerprint.
"""

from .money_digest_r2_l6 import _rows


def hackmoney_money_rows(makerspace_id, using="default"):
    from django.apps import apps

    get = apps.get_model
    parts = {
        "event_prize_shares": _rows(get("events.HackathonPrizeShare"), using,
                                    ("id", "award_id", "member_id", "amount", "state"), makerspace_id=makerspace_id),
        "event_prize_outcomes": _rows(get("events.HackathonPrizeOutcome"), using,
                                      ("id", "award_id", "kind", "amount", "currency", "ledger_entry_id"),
                                      makerspace_id=makerspace_id),
        "event_money_settings": _rows(get("payments.EventMoneySettings"), using,
                                      ("id", "prize_tds_enabled", "prize_tds_rate", "prize_tds_threshold"),
                                      makerspace_id=makerspace_id),
        # G10: the deposit a confirmed place is charged, and whether its settlement batch ran.
        "event_deposit_options": [row for row in _rows(
            get("events.HackathonProgrammeOptions"), using, ("id", "event_id", "deposit_amount", "deposits_settled_at"),
            event__makerspace_id=makerspace_id) if row["deposit_amount"] != "None"],
    }
    return {key: rows for key, rows in parts.items() if rows}
