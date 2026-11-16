"""Lane L18 rows in the capture-bound money fingerprint.

A gift's status decides whether its charge is owed, a live pledge raises the next charge on
its own clock, and a sponsorship charge is money owed. All three participate; each key is
omitted when empty, so a space that never took a gift keeps its existing fingerprint.
"""


def _rows(model, using, values, **lookup):
    from apps.backup.capture_managers import every_row
    return [{key: str(value) for key, value in row.items()}
            for row in every_row(model).using(using).filter(**lookup).order_by("pk").values(*values)]


def l18_money_rows(makerspace_id, using="default"):
    from django.apps import apps

    get = apps.get_model
    parts = {
        "donations": _rows(get("payments.Donation"), using, ("id", "status", "amount", "currency", "paid_at"),
                           makerspace_id=makerspace_id),
        "donation_pledges": _rows(get("payments.DonationPledge"), using,
                                  ("id", "status", "amount", "currency", "interval", "next_due_on"),
                                  makerspace_id=makerspace_id),
        "sponsorship_charges": _rows(get("payments.SponsorshipCharge"), using, ("id", "amount", "currency"),
                                     makerspace_id=makerspace_id),
    }
    return {key: rows for key, rows in parts.items() if rows}
