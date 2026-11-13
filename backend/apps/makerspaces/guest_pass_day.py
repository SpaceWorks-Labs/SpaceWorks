"""Decision 223(b)/(e): day-pass products and the sale.

The price is a debt recorded FIRST under `charges.membership` (`charge_tracking_enabled`),
independent of the payments rail; the online checkout is best-effort afterwards, only when
`online_payments_enabled`. With charges off a priced product cannot be sold (it can only be
free). A paid day pass gives no credit toward joining; staff may waive the joining fee by hand.
The pass stays unusable until its charge is settled or waived (`guest_pass_queries.payment_cleared`),
so a pending debt never unlocks anything.
"""
from django.utils.translation import gettext
import logging
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.audit import services as audit
from apps.makerspaces.guest_pass_issue import check_holder, create_pass, day_window, replay_pass
from apps.makerspaces.guest_pass_policy import GuestPassError, policy_for
from apps.makerspaces.membership_features import require_membership_feature_locked
from apps.makerspaces.models import DayPassProduct, GuestPass

logger = logging.getLogger(__name__)

PRODUCT_FIELDS = ("name", "amount", "currency", "entitlements", "daily_cap", "is_public", "is_active")


def save_product(actor, makerspace, data, product=None):
    """Create or edit a product (manage_makerspace is checked by the view). Audited."""
    unknown = set(data) - set(PRODUCT_FIELDS)
    if unknown:
        raise ValidationError({name: "Unknown field." for name in sorted(unknown)})
    with transaction.atomic():
        makerspace = require_membership_feature_locked(makerspace, "day_passes")
        creating = product is None
        product = product or DayPassProduct(makerspace=makerspace)
        if product.archived_at is not None:
            raise GuestPassError("product_archived", gettext("An archived product cannot be edited."))
        for name, value in data.items():
            setattr(product, name, value)
        if product.amount > 0:
            from apps.payments.availability import charge_tracking_enabled
            if not charge_tracking_enabled(makerspace, "membership"):
                raise GuestPassError("charges_off", gettext("Turn on membership charges before pricing a day pass."))
        product.full_clean(exclude=["makerspace"])
        product.save()
        audit.record(actor, "membership.day_pass_product_saved", makerspace=makerspace, target=product,
                     meta={"created": creating, "fields": sorted(data)})
    return product


def archive_product(actor, product):
    """Archived, never deleted: sold passes keep pointing at it (219(h) pattern)."""
    with transaction.atomic():
        makerspace = require_membership_feature_locked(product.makerspace_id, "day_passes")
        product = DayPassProduct.objects.select_for_update().get(pk=product.pk, makerspace=makerspace)
        if product.archived_at is None:
            product.archived_at, product.is_active = timezone.now(), False
            product.save(update_fields=["archived_at", "is_active", "updated_at"])
            audit.record(actor, "membership.day_pass_product_archived", makerspace=makerspace, target=product)
    return product


def _check_caps(makerspace, product, day, policy):
    sold = GuestPass.objects.filter(makerspace=makerspace, kind=GuestPass.Kind.DAY, pass_date=day).exclude(
        status=GuestPass.Status.REVOKED)
    # m19: walk-in / staff free passes carry no product and never count toward the day-pass cap.
    if policy.day_pass_daily_cap and sold.filter(product__isnull=False).count() >= policy.day_pass_daily_cap:
        raise GuestPassError("day_pass_sold_out", gettext("Day passes are sold out for that day."))
    if product.daily_cap and sold.filter(product=product).count() >= product.daily_cap:
        raise GuestPassError("day_pass_sold_out", gettext("This day pass is sold out for that day."))


def sell_day_pass(actor, makerspace, holder, product, *, day=None, operation_id=None, now=None):
    """Buy (actor == holder) or desk-sell (staff) a day pass. Returns `(pass, payment_or_None)`.

    A free product issues a usable pass at once. A priced one records a pending `guest_pass`
    charge in the same transaction; a failure to RECORD it rolls the pass back (a debt is never
    silently dropped), while a failure to start the online checkout only logs.
    """
    from apps.payments.availability import charge_tracking_enabled, online_payments_enabled
    from apps.payments.models import MakerspacePaymentSettings, Payment
    from apps.payments.services import create_payment

    now = now or timezone.now()
    with transaction.atomic():
        makerspace = require_membership_feature_locked(makerspace, "day_passes")
        product = DayPassProduct.objects.select_for_update().filter(pk=product.pk, makerspace=makerspace).first()
        if product is None or not product.is_active or product.archived_at is not None:
            raise GuestPassError("product_unavailable", gettext("That day pass is not on sale."), status_code=404)
        replay = replay_pass(makerspace, holder, operation_id)
        if replay is not None:  # a retry returns the first call's pass and its charge, whatever the caps say now
            return replay, Payment.objects.filter(
                makerspace=makerspace, subject_id=replay.pk, subject_type=Payment.SubjectType.GUEST_PASS).first()
        priced = product.amount > Decimal("0")
        if priced and not charge_tracking_enabled(makerspace, "membership"):
            raise GuestPassError("charges_off", gettext("This space is not charging for passes; ask staff for a free pass."))
        start, end, pass_day = day_window(makerspace, day, now)
        policy = policy_for(makerspace)
        check_holder(holder, makerspace)
        _check_caps(makerspace, product, pass_day, policy)
        row, created = create_pass(makerspace, holder, GuestPass.Kind.DAY, start, end, pass_day, issuer=actor,
                                   product=product, operation_id=operation_id, policy=policy,
                                   template=product.entitlements)
        payment = Payment.objects.filter(makerspace=makerspace, subject_id=row.pk,
                                         subject_type=Payment.SubjectType.GUEST_PASS).first()
        if priced and payment is None:
            currency = product.currency or MakerspacePaymentSettings.for_makerspace(makerspace).default_currency
            try:
                with transaction.atomic():
                    payment = create_payment(
                        makerspace=makerspace, subject_type=Payment.SubjectType.GUEST_PASS, subject_id=row.pk,
                        member=holder, amount=product.amount, currency=currency, created_by=actor,
                        subject_label=f"Day pass: {product.name}", due_at=start,
                    )
            except IntegrityError:
                payment = Payment.objects.get(makerspace=makerspace, subject_id=row.pk,
                                              subject_type=Payment.SubjectType.GUEST_PASS)
            audit.record(actor, "membership.guest_pass_charge_raised", makerspace=makerspace, target=row,
                         meta={"payment_id": payment.pk, "product_id": product.pk})
            if online_payments_enabled(makerspace, "membership"):
                from apps.makerspaces.membership_payments import _schedule_checkout
                try:
                    _schedule_checkout(payment)
                except Exception:  # noqa: BLE001 - the recorded debt stands; only the rail failed
                    logger.warning("guest_pass_checkout_schedule_failed", extra={"payment_id": payment.pk})
    return row, payment


def public_products(makerspace):
    """Products a visitor may see: public, active, never archived. No sales counts leak."""
    from apps.payments.availability import charge_tracking_enabled
    rows = DayPassProduct.objects.filter(makerspace=makerspace, is_public=True, is_active=True,
                                         archived_at__isnull=True)
    # With charges off a priced product cannot be sold, so it is not offered either.
    return rows if charge_tracking_enabled(makerspace, "membership") else rows.filter(amount=0)
