"""One space's rate card for one domain, and per-component rate resolution (lane L15).

Resolution for one component on one item, most specific first:

1. the item's own legacy price field above 0 (a room's `payment_amount`, a product's
   `deposit_amount`): that IS the item's custom price, edited in the item's own form;
2. a `PriceOverride` row on the item (or a more specific item, e.g. a material pool
   before its machine): `free` is 0, `custom` is its amount;
3. a domain-specific middle level (a machine type's `MakerspaceMachineTypePricing`);
4. the space rate card: `PricingDefaultLine`, or the legacy space fields for the deposit
   and late fee; a domain in `free` mode resolves to 0 here.

0 or empty on an item means "inherit the default" (A13). With the `charges.pricing`
capability off, levels 2 and 4's new lines are skipped: only the release-1 fields apply.
"""

from dataclasses import dataclass
from decimal import Decimal

from apps.makerspaces.platform import feature_enabled
from apps.payments.models_pricing import PriceOverride, PricingDefault

ZERO = Decimal("0")
PRICING_FEATURE = "charges.pricing"


@dataclass(frozen=True)
class Rate:
    amount: Decimal = ZERO
    source: str = "none"
    cap: Decimal | None = None
    grace: int = 0
    increment: int = 0
    minimum: int = 0

    @property
    def free(self):
        return self.amount <= 0


NONE = Rate()


class RateCard:
    def __init__(self, makerspace, domain):
        self.makerspace = makerspace
        self.domain = domain
        self.enabled = feature_enabled(makerspace, PRICING_FEATURE)
        self.row = PricingDefault.objects.filter(makerspace=makerspace, domain=domain).first()
        self.lines = ({line.component: line for line in self.row.lines.all()}
                      if self.row is not None and self.enabled else {})
        self._overrides = {}
        self._payment_settings = None

    # --- the space level -------------------------------------------------------------
    @property
    def payment_settings(self):
        if self._payment_settings is None:
            from apps.payments.models import MakerspacePaymentSettings
            self._payment_settings = MakerspacePaymentSettings.for_makerspace(self.makerspace)
        return self._payment_settings

    @property
    def currency(self):
        return self.payment_settings.default_currency

    @property
    def mode(self):
        """Stored mode; without a row, "paid" only when a legacy space amount is set."""
        if self.row is not None and self.enabled:
            return self.row.mode
        from apps.payments.pricing.adapters import legacy_defaults
        legacy = legacy_defaults(self)
        return PricingDefault.Mode.PAID if any(rate.amount > 0 for rate in legacy.values()) else PricingDefault.Mode.FREE

    @property
    def rental_timing(self):
        if self.row is not None and self.enabled and self.row.rental_timing:
            return self.row.rental_timing
        return PricingDefault.RentalTiming.AT_CHECKOUT

    @property
    def failed_job_charge(self):
        if self.row is not None and self.enabled and self.row.failed_job_charge:
            return self.row.failed_job_charge
        return PricingDefault.FailedJobCharge.NONE

    def default(self, component):
        """The space rate, honouring free mode. Legacy space fields fill in where they exist."""
        from apps.payments.pricing.adapters import legacy_defaults
        if self.row is not None and self.enabled and self.row.mode == PricingDefault.Mode.FREE:
            return Rate(source="free_default")
        line = self.lines.get(component)
        if line is not None:
            return Rate(amount=line.amount, source="default", cap=line.cap, grace=line.grace_units,
                        increment=line.billing_increment, minimum=line.minimum)
        return legacy_defaults(self).get(component, NONE)

    # --- the item level --------------------------------------------------------------
    def prefetch(self, target_type, ids):
        ids = {int(pk) for pk in ids if pk is not None} - {key[1] for key in self._overrides if key[0] == target_type}
        if not ids:
            return
        for pk in ids:
            self._overrides.setdefault((target_type, pk), {})
        if not self.enabled:
            return
        field = PriceOverride.FIELDS[target_type]
        rows = PriceOverride.objects.filter(makerspace=self.makerspace, target_type=target_type,
                                            **{f"{field}_id__in": ids})
        for row in rows:
            self._overrides[(target_type, row.target_id)][row.component] = row

    def override(self, component, target_type, target_id):
        if target_id is None:
            return None
        self.prefetch(target_type, [target_id])
        return self._overrides[(target_type, int(target_id))].get(component)

    def resolve(self, component, targets=(), *, legacy_item=None, middle=None):
        """The rate for `component` on the most specific of `targets` ((type, id) pairs)."""
        if legacy_item is not None and Decimal(legacy_item) > 0:
            return Rate(amount=Decimal(legacy_item), source="item")
        for target_type, target_id in targets:
            row = self.override(component, target_type, target_id)
            if row is None or row.mode == PriceOverride.Mode.INHERIT:
                continue
            if row.mode == PriceOverride.Mode.FREE:
                return Rate(source="override_free")
            default = self.default(component)
            return Rate(amount=row.amount, source="override", cap=row.cap if row.cap is not None else default.cap,
                        grace=default.grace, increment=default.increment, minimum=default.minimum)
        if middle is not None:
            return middle
        return self.default(component)
