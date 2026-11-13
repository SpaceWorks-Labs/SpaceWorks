"""Lane L15 rows in the capture-bound money fingerprint.

A loan fee waiver decides whether charges not yet raised are owed at all, and a waiver
written after a capture can turn a debt into a refund case. Waivers (and revocations)
therefore participate. A charge's frozen `pricing_snapshot` cannot change after insert,
so the payment rows already cover it. Omitted when empty, so a capture taken by a space
that never waived a fee keeps its existing fingerprint.
"""


def l15_money_rows(makerspace_id, using="default"):
    from django.apps import apps

    Waiver = apps.get_model("payments.LoanFeeWaiver")
    rows = [{key: str(value) for key, value in row.items()} for row in
            Waiver.objects.using(using).filter(makerspace_id=makerspace_id).order_by("pk")
            .values("id", "request_id", "components", "revokes_id")]
    return {"loan_fee_waivers": rows} if rows else {}
