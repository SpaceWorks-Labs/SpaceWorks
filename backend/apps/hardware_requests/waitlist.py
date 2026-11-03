"""Loan waitlist (loans.waitlist): strict first come, first served, per product.

When free stock appears the head entry is offered and the units are HELD for it
through the availability module, so nobody else can take them while the offer is open.
The member claims the offer by submitting a request that names the entry; accepting
that request converts the hold into its reservation inside one transaction. Offers that
are not claimed in time lapse and the next entry is offered.
"""

import logging
from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.audit import services as audit
from apps.hardware_requests.models_loans import LoanReservationPolicy, LoanWaitlistEntry as Entry
from apps.inventory import availability

logger = logging.getLogger(__name__)
FEATURE = "loans.waitlist"


def _locked(entry):
    return Entry.objects.select_for_update().select_related("makerspace").get(pk=entry.pk)


def _release(entry, status, *, actor=None):
    if entry.held_quantity:
        availability.release_waitlist_hold(entry.product_id, entry.held_quantity)
    entry.held_quantity, entry.status, entry.closed_at = 0, status, timezone.now()
    entry.save(update_fields=["held_quantity", "status", "closed_at", "updated_at"])
    if status == Entry.Status.CANCELLED:
        audit.record(actor, "inventory.waitlist_left", makerspace=entry.makerspace, target=entry,
                     meta={"entry_id": entry.pk, "product_id": entry.product_id})
    else:
        audit.record(actor, "inventory.waitlist_lapsed", makerspace=entry.makerspace, target=entry,
                     meta={"entry_id": entry.pk, "product_id": entry.product_id})


def require_waitlist_member(user, makerspace):
    """The borrow request's identity rule minus presence: joining is planning, not arriving."""
    from apps.accounts.account_kind_guards import require_member_account
    from apps.makerspaces.platform import module_enabled
    from apps.presence.guard import require_active_account, require_active_member
    require_member_account(user)
    if module_enabled(makerspace, "membership"):
        require_active_member(user, makerspace)
    else:
        require_active_account(user, makerspace)


@transaction.atomic
def join(user, product, quantity):
    from apps.makerspaces.guards import require_feature
    require_feature(product.makerspace, "loans.enabled")
    require_feature(product.makerspace, FEATURE)
    require_waitlist_member(user, product.makerspace)
    product = type(product).objects.select_for_update().get(pk=product.pk)
    if not product.is_public or product.is_archived or product.is_consumable:
        raise ValidationError({"detail": "This item cannot be waitlisted."})
    ahead = Entry.objects.filter(product=product, status__in=Entry.ACTIVE)
    if product.available_quantity >= quantity and not ahead.exists():
        raise ValidationError({"detail": "This item is available now; request it instead."})
    if ahead.filter(user=user).exists():
        raise ValidationError({"detail": "You are already on the waitlist for this item."})
    entry = Entry.objects.create(makerspace=product.makerspace, product=product, user=user, quantity=quantity)
    audit.record(user, "inventory.waitlist_joined", makerspace=product.makerspace, target=entry,
                 meta={"entry_id": entry.pk, "product_id": product.pk, "quantity": quantity})
    schedule_offers(product.pk)
    return entry


@transaction.atomic
def leave(user, entry):
    entry = _locked(entry)
    if entry.user_id != user.pk or entry.status not in (Entry.Status.WAITING, Entry.Status.OFFERED):
        raise ValidationError({"detail": "This waitlist entry cannot be left."})
    _release(entry, Entry.Status.CANCELLED, actor=user)
    schedule_offers(entry.product_id)
    return entry


def position(entry):
    return Entry.objects.filter(product_id=entry.product_id, status__in=Entry.ACTIVE).filter(
        created_at__lt=entry.created_at).count() + 1


def schedule_offers(product_id):
    transaction.on_commit(lambda: offer_next(product_id))


def stock_rose(product):
    """Availability observer: free units appeared, so the head of the line may be offered."""
    # One indexed query when nobody waits; offer_next re-checks the switch under lock.
    if Entry.objects.filter(product_id=product.pk, status=Entry.Status.WAITING).exists():
        schedule_offers(product.pk)


def offer_next(product_id):
    """Offer free units to waiting entries, head first; strict order (no skipping)."""
    from apps.inventory.models import InventoryProduct
    try:
        with transaction.atomic():
            product = InventoryProduct.objects.select_for_update().select_related("makerspace").get(pk=product_id)
            from apps.makerspaces.platform import feature_enabled
            if not feature_enabled(product.makerspace, FEATURE):
                return []
            from apps.tenant_migration.gate_runtime import assert_write_allowed
            assert_write_allowed(product.makerspace_id)
            hours = LoanReservationPolicy.for_makerspace(product.makerspace).waitlist_offer_hours
            offered = []
            for entry in Entry.objects.select_for_update().filter(
                    product_id=product_id, status=Entry.Status.WAITING).order_by("created_at", "id"):
                product.refresh_from_db(fields=["available_quantity", "reserved_quantity"])
                if product.available_quantity < entry.quantity:
                    break
                availability.hold_for_waitlist(product_id, entry.quantity)
                now = timezone.now()
                entry.status, entry.held_quantity = Entry.Status.OFFERED, entry.quantity
                entry.offered_at, entry.offer_expires_at = now, now + timedelta(hours=hours)
                entry.save(update_fields=["status", "held_quantity", "offered_at", "offer_expires_at", "updated_at"])
                audit.record(None, "inventory.waitlist_offered", makerspace=product.makerspace, target=entry,
                             meta={"entry_id": entry.pk, "product_id": product_id, "quantity": entry.quantity})
                from apps.hardware_requests.notifications_loans import notify_waitlist_offer
                notify_waitlist_offer(entry)
                offered.append(entry.pk)
            return offered
    except Exception:
        logger.exception("Waitlist offer failed for product %s", product_id)
        return []


def lapse_due_offers(*, now=None, limit=200):
    from apps.accounts import rbac
    from apps.tenant_migration.gate_runtime import fanout_tenant_write
    now = now or timezone.now()
    counts, lapsed = {"skipped": 0}, 0
    due = rbac.scope_for_scheduled_work(Entry.objects.filter(
        status=Entry.Status.OFFERED, offer_expires_at__lte=now)).order_by("offer_expires_at", "pk")[:limit]
    for entry in due:
        with fanout_tenant_write(entry.makerspace_id, operation="loan_waitlist_lapse", counts=counts) as go:
            if not go:
                continue
            try:
                with transaction.atomic():
                    entry = _locked(entry)
                    if entry.status != Entry.Status.OFFERED or entry.offer_expires_at > now:
                        continue
                    _release(entry, Entry.Status.LAPSED)
                    schedule_offers(entry.product_id)
                    lapsed += 1
            except Exception:
                logger.exception("Waitlist lapse failed for entry %s", entry.pk)
    return lapsed


def claim(entry_id, user, items):
    """Inside submit: bind the member's open offer to the new request's items."""
    entry = Entry.objects.select_for_update().filter(pk=entry_id, user=user, status=Entry.Status.OFFERED).first()
    if entry is None:
        raise ValidationError({"waitlist_entry_id": "This waitlist offer is not open."})
    wanted = next((item["quantity"] for item in items if item["product"].pk == entry.product_id), 0)
    if not 1 <= wanted <= entry.held_quantity:
        raise ValidationError({"waitlist_entry_id": "Request the offered item, up to the offered quantity."})
    return entry


def bind_claim(entry, request):
    entry.status, entry.request = Entry.Status.CLAIMED, request
    entry.save(update_fields=["status", "request", "updated_at"])
    audit.record(request.requester, "inventory.waitlist_claimed", makerspace=request.makerspace, target=entry,
                 meta={"entry_id": entry.pk, "product_id": entry.product_id, "request_id": request.pk})


def convert_claim(request):
    """Inside accept, before reserving: free the claimed hold so the reservation takes it."""
    entry = Entry.objects.select_for_update().filter(request=request, status=Entry.Status.CLAIMED).first()
    if entry is None:
        return None
    availability.release_waitlist_hold(entry.product_id, entry.held_quantity)
    entry.held_quantity, entry.status, entry.closed_at = 0, Entry.Status.FULFILLED, timezone.now()
    entry.save(update_fields=["held_quantity", "status", "closed_at", "updated_at"])
    return entry


def release_claim(request):
    """On reject/cancel/expiry: a still-claimed hold goes back and the queue moves on."""
    entry = Entry.objects.select_for_update().filter(request=request, status=Entry.Status.CLAIMED).first()
    if entry is not None:
        _release(entry, Entry.Status.LAPSED)
        schedule_offers(entry.product_id)
    return entry


def someone_waiting(product_ids):
    return Entry.objects.filter(product_id__in=list(product_ids),
                                status__in=(Entry.Status.WAITING, Entry.Status.OFFERED)).exists()
