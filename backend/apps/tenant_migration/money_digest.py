"""A capture-bound fingerprint of a tenant's unsettled money.

Pending payments travel in a portable dump now (owner decision D5). They could not
before: a single pending row refused the whole dump, which made a dump nearly
impossible for any space that tracks what members owe -- and tracking is on by default
since charges stopped depending on the payments module.

Letting them travel needs one protection the old refusal gave for free. A capture
freezes the database under an exclusive gate and then REOPENS the source, so between
capture and cutover the source can settle a captured debt, raise a new one, or start a
rail. A dump carrying a debt the source has since collected would let the target bill
the member a second time.

So the capture records a digest over exactly the rows that could drift -- pending
payments and the settlement chain that explains them -- and the cutover recomputes it
against the live source. A mismatch is not repairable by merging: the artifact was
derived from the frozen image, so the only honest answer is to recapture. That is what
`assert_money_unchanged` refuses with.

Terminal payments themselves are immutable and excluded. Their refund lines can still
grow or settle, so those lines participate alongside the settlement receipts.
"""

import hashlib
import json


def money_fingerprint(makerspace_id, *, using="default"):
    """Canonical digest of the tenant's unsettled money, plus its receipts.

    Ordered by primary key and rendered with sorted keys, so the same database state
    always produces the same digest regardless of query plan or row order.
    """
    from django.apps import apps

    Payment = apps.get_model("payments.Payment")
    ManualSettlement = apps.get_model("payments.ManualSettlement")
    Refund = apps.get_model("payments.Refund")
    Document = apps.get_model("payments.PaymentDocument")

    # The live-rail columns are here for a case that is easy to miss. A pending row can
    # already carry a provider while holding no handle -- a checkout whose creation
    # failed, or one that expired -- and the reopened source can then mint a fresh
    # session or intent for it. `status`, `amount` and `provider` all sit still through
    # that, so on their own the digest matched and publication handed out an artifact
    # whose handles were stripped while the source stayed payable: the very double
    # collection `preflight._check_live_checkouts` refuses before the freeze. Same field
    # set as that check, plus the expiry that makes a handle inert and the rail label,
    # so a rail appearing after capture is drift like any other.
    payments = list(
        Payment._base_manager.using(using)
        .filter(makerspace_id=makerspace_id, status="pending")
        .order_by("pk")
        .values(
            "id",
            "status",
            "amount",
            "currency",
            "due_at",
            "provider",
            "online_rail",
            "external_order_id",
            "checkout_url",
            "stripe_checkout_session_id",
            "stripe_checkout_url",
            "stripe_checkout_session_expired_at",
            "stripe_payment_intent_id",
        )
    )
    # A receipt appearing (or being amended) against a captured pending row means that
    # row was settled at the source after capture -- exactly the drift this catches.
    settlements = list(
        ManualSettlement.objects.using(using)
        .filter(payment__makerspace_id=makerspace_id)
        .order_by("pk")
        .values("id", "payment_id", "method", "received_at", "amends_id")
    )
    payload = {
        "pending_payments": [
            {key: str(value) for key, value in row.items()} for row in payments
        ],
        "settlements": [
            {key: str(value) for key, value in row.items()} for row in settlements
        ],
    }
    # Terminal payments stay still while their refund ledger can grow. Returning a
    # captured cash deposit at the source must refuse publication of the stale dump.
    # Omit the empty key to preserve fingerprints from captures with no refunds.
    refunds = list(Refund.objects.using(using).filter(payment__makerspace_id=makerspace_id)
                   .order_by("pk").values("id", "payment_id", "amount", "currency", "status",
                                           "provider", "method", "reference", "refunded_at", "settled_at", "amends_id"))
    if refunds:
        payload["refunds"] = [{key: str(value) for key, value in row.items()} for row in refunds]
    # An undecided or approved refund entitlement is money the source may still send
    # back. Approving, declining or opening one after capture is drift. Omitted when
    # empty so captures with no cases keep their fingerprint.
    Case = apps.get_model("payments.RefundCase")
    cases = list(Case.objects.using(using).filter(
        payment__makerspace_id=makerspace_id, status__in=("open", "approved", "approval_failed"),
    ).order_by("pk").values("id", "payment_id", "kind", "status", "due_amount", "approved_amount", "refund_id"))
    if cases:
        payload["refund_cases"] = [{key: str(value) for key, value in row.items()} for row in cases]
    documents = list(Document.objects.using(using).filter(makerspace_id=makerspace_id)
                     .order_by("pk").values("id", "payment_id", "sequence", "number", "kind", "amount", "currency"))
    if documents:
        payload["documents"] = documents
    Billing = apps.get_model("payments.MakerspaceBillingSettings")
    counters = list(Billing.objects.using(using).filter(makerspace_id=makerspace_id)
                    .values("next_document_number", "number_prefix", "next_bill_number", "bill_prefix"))
    if counters:
        payload["document_counter"] = counters
    from .money_digest_l5 import l5_money_rows

    payload.update(l5_money_rows(makerspace_id, using))
    from .money_digest_r2_l15 import l15_money_rows

    payload.update(l15_money_rows(makerspace_id, using))
    from .money_digest_r2_l6 import l6_money_rows

    payload.update(l6_money_rows(makerspace_id, using))
    from .money_digest_r2_l21b import l21b_money_rows

    payload.update(l21b_money_rows(makerspace_id, using))
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(encoded).hexdigest()


class MoneyDriftRefused(Exception):
    """The source's unsettled money moved after the capture that produced the dump."""

    def __init__(self, expected, actual):
        self.expected = expected
        self.actual = actual
        super().__init__(
            "Source money state changed after capture: a charge was settled, raised, "
            "refunded, amended, or given a live payment rail. The artifact was derived "
            "from the frozen image and cannot be merged forward -- recapture the tenant."
        )


def assert_money_unchanged(capture, *, using="default"):
    """Refuse a cutover whose dump no longer describes the source's obligations.

    A capture taken before this field existed carries an empty digest; those are not
    revalidated, because a blank is "not recorded", not "nothing was owed", and
    inventing a comparison would refuse every pre-existing capture.
    """
    expected = capture.money_fingerprint_sha256
    if not expected:
        return None
    actual = money_fingerprint(capture.source_makerspace_id, using=using)
    if actual != expected:
        raise MoneyDriftRefused(expected, actual)
    return actual
