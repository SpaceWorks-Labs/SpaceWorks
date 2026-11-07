from django.utils.translation import gettext, gettext_noop
from django.core.exceptions import ValidationError
from django.db import models

from apps.payments.models_settings import currency_validator


class Payment(models.Model):
    class SubjectType(models.TextChoices):
        MACHINE_SERVICE_REQUEST = "machine_service_request", gettext_noop("Machine service request")
        BOOKING = "booking", "Booking"
        EVENT_REGISTRATION = "event_registration", gettext_noop("Event registration")
        MAKERSPACE_MEMBERSHIP = "makerspace_membership", gettext_noop("Makerspace membership")
        # subject_id is the `makerspaces.MembershipTerm` pk: the membership pk is already
        # taken by the dues charge above, and one term gets exactly one renewal charge.
        MEMBERSHIP_TERM = "membership_term", gettext_noop("Membership renewal")
        MEMBERSHIP_REQUEST = "membership_request", gettext_noop("Membership admission")
        # Loan charges (forward plan phase 6). subject_id is the HardwareRequest id, so
        # the one-per-subject constraint gives one deposit and one late fee per loan.
        LOAN_DEPOSIT = "loan_deposit", gettext_noop("Loan deposit")
        LOAN_LATE_FEE = "loan_late_fee", gettext_noop("Loan late fee")
        # Lane L15 (#84/#85). Rental is one per loan (subject_id = HardwareRequest id);
        # damage and lost are one per RequesterAccountability row (subject_id = its id).
        LOAN_RENTAL = "loan_rental", gettext_noop("Loan rental")
        LOAN_DAMAGE = "loan_damage", gettext_noop("Loan damage charge")
        LOAN_LOST = "loan_lost", gettext_noop("Lost item charge")
        # Lane L23 (#158): one metered machine session; subject_id is the MachineSession id.
        MACHINE_SESSION = "machine_session", gettext_noop("Machine session")
        # Lane L6. An order is one buyer's several tickets (subject_id = EventOrder id); a
        # venue fee is an outside organiser's hosting charge (subject_id = EventVenueFee id).
        EVENT_ORDER = "event_order", gettext_noop("Event ticket order")
        EVENT_VENUE_FEE = "event_venue_fee", gettext_noop("Event venue fee")
        # Lane L18. A donation (one-off, or one period of a pledge; subject_id = Donation id)
        # and a sponsor's agreed payment (subject_id = SponsorshipCharge id).
        DONATION = "donation", "Donation"
        SPONSORSHIP = "sponsorship", "Sponsorship"
        # Lane L21b. A hackathon project's entry fee (subject_id = HackathonSubmission id) and a
        # paid team's one charge on its leader (subject_id = HackathonTeam id, C-39).
        SUBMISSION_FEE = "submission_fee", gettext_noop("Project entry fee")
        TEAM_REGISTRATION = "team_registration", gettext_noop("Team registration")
        # Hack-money G10: an optional refundable commitment deposit (subject_id = EventRegistration id).
        EVENT_DEPOSIT = "event_deposit", gettext_noop("Event deposit")
        # Lane L22. One shop order (online or a front-desk sale; subject_id = ShopOrder id).
        SHOP_ORDER = "shop_order", gettext_noop("Shop order")
        # #184: a term staff open from the console (subject_id = that MembershipTerm pk). Not
        # MEMBERSHIP_TERM: that subject id already names the term whose RENEWAL is charged.
        MEMBERSHIP_TERM_START = "membership_term_start", gettext_noop("Membership term")

    #: Subjects whose subject_id is the HardwareRequest id.
    LOAN_SUBJECT_TYPES = ("loan_deposit", "loan_late_fee", "loan_rental")
    #: Subjects whose subject_id is a RequesterAccountability row of a loan.
    LOAN_ACCOUNTABILITY_SUBJECT_TYPES = ("loan_damage", "loan_lost")
    #: Lane L6: event money that is not one registration's own charge.
    EVENT_SUBJECT_TYPES = ("event_registration", "event_order", "event_venue_fee", "submission_fee", "team_registration",
                           "event_deposit")
    #: Lanes L18 and L22: money that may belong to no account (a guest donor, a sponsor
    #: organisation, a guest shop buyer or an anonymous desk sale).
    ACCOUNTLESS_SUBJECT_TYPES = ("donation", "sponsorship", "shop_order")
    #: Lane L18: a gift is never a taxable supply, so no tax is frozen on top of it.
    UNTAXED_SUBJECT_TYPES = ("donation",)

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PAID_ONLINE = "paid_online", gettext_noop("Paid online")
        PAID_OFFLINE = "paid_offline", gettext_noop("Paid offline")
        WAIVED = "waived", "Waived"
        CANCELED = "canceled", "Canceled"

    class StripeProvider(models.TextChoices):
        RAW = "raw", gettext_noop("Makerspace raw credentials")
        CONNECT = "connect", gettext_noop("Stripe Connect")

    class Provider(models.TextChoices):
        """Which vendor holds this charge.

        Distinct from `stripe_provider`, which says how STRIPE credentials were
        resolved (raw vs Connect) and is meaningless for any other vendor.
        """

        STRIPE = "stripe", "Stripe"
        RAZORPAY = "razorpay", "Razorpay"
        # A debt raised while the space had no gateway configured. It is real money owed
        # and fully reconcilable offline; it simply has no rail behind it yet. The first
        # checkout that reaches a provider claims the row (services._claim_provider), and
        # a DB trigger permits that transition exactly once. Without this state such a row
        # would be stamped `stripe` and could never be claimed by a gateway configured
        # later, because provider provenance is immutable.
        UNCLAIMED = "unclaimed", gettext_noop("No online rail")

    class OnlineRail(models.TextChoices):
        CHECKOUT = 'checkout', gettext_noop('Stripe Checkout')
        NATIVE_PAYMENT_INTENT = 'native_payment_intent', gettext_noop('Native payment intent')

    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.PROTECT, related_name="payments")
    subject_type = models.CharField(max_length=48, choices=SubjectType.choices)
    subject_id = models.PositiveBigIntegerField()
    member = models.ForeignKey("accounts.User", null=True, blank=True, on_delete=models.PROTECT, related_name="payments")
    # Which makerspace's member area may surface this charge, beyond the owning space.
    # A collaborative event is hosted by A, so the Payment is A's (ownership decides which
    # Stripe account is charged), but the member reached it through B and has no membership
    # at A. This column is deliberately NOT on EventRegistration: a purge clears that row's
    # provenance (activity history is what a purge is for) and the host's own purge deletes
    # the registration outright, either of which would strand a receipt or a payable debt.
    # SET_NULL, not PROTECT: this is a routing hint, not ownership -- `makerspace` is that.
    via_makerspace = models.ForeignKey(
        "makerspaces.Makerspace", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="payments_via",
    )
    # Snapshotted at creation so a receipt stays readable after its subject row is purged.
    # Same idiom as `destination_label` on notification delivery logs. Financial metadata,
    # so it must never carry PII -- callers pass an event title, a space name or a service
    # title, never a person's name, contact details or custom-form answers.
    subject_label = models.CharField(max_length=255, blank=True, default="")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, validators=[currency_validator])
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    due_at = models.DateTimeField(null=True, blank=True)
    # Provider-agnostic columns (phase 4). The `stripe_*` columns below are retained as
    # read-only historic, exactly as `MachineServiceRequest.payment_*` was when Payment
    # took over: rows are immutable once terminal, so a migration may only ADD nullable
    # columns and may never rewrite what is already there.
    provider = models.CharField(
        max_length=16, choices=Provider.choices, default=Provider.STRIPE
    )
    external_order_id = models.CharField(max_length=255, null=True, blank=True)
    external_payment_id = models.CharField(max_length=255, null=True, blank=True)
    checkout_url = models.URLField(blank=True, default="")
    stripe_provider = models.CharField(max_length=16, choices=StripeProvider.choices, default=StripeProvider.RAW)
    stripe_connected_account_id = models.CharField(max_length=255, null=True, blank=True)
    stripe_application_fee_amount = models.PositiveBigIntegerField(default=0)
    online_rail = models.CharField(
        max_length=32,
        choices=OnlineRail.choices,
        null=True,
        blank=True,
    )
    stripe_checkout_session_id = models.CharField(max_length=255, null=True, blank=True, unique=True)
    stripe_checkout_url = models.URLField(blank=True, default="")
    stripe_checkout_session_expired_at = models.DateTimeField(null=True, blank=True)
    stripe_payment_intent_id = models.CharField(max_length=255, null=True, blank=True, unique=True)
    # Lane L5. The tax policy frozen when the charge was raised (NULL with tax off), and
    # the provider's display label for how it was paid ("Visa ••4242"). Neither is ever
    # rewritten: the snapshot is insert-only and the label fills once, from blank.
    tax_snapshot = models.JSONField(null=True, blank=True, default=None)
    method_label = models.CharField(max_length=64, blank=True, default="")
    # Lane L15. The frozen quote (lines, discount, waiver, sources, digest) the amount was
    # computed from; `{}` for charges raised without the pricing kernel. Insert-only.
    pricing_snapshot = models.JSONField(default=dict, blank=True)
    created_by = models.ForeignKey("accounts.User", on_delete=models.PROTECT, related_name="created_payments")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["makerspace", "status", "due_at"], name="payment_ms_status_due_idx"),
            models.Index(
                fields=["via_makerspace", "member"],
                name="payment_via_makerspace_member_idx",
            ),
        ]
        constraints = [
            models.UniqueConstraint(fields=["makerspace", "subject_type", "subject_id"], name="payment_one_per_subject"),
            # Scoped BY PROVIDER: two vendors are free to mint the same opaque id, and a
            # global unique index would make the second one unstorable. Partial, because
            # NULL means "no checkout raised yet" and many rows sit in that state.
            models.UniqueConstraint(
                fields=["provider", "external_order_id"],
                name="payment_external_order_once_per_provider",
                condition=models.Q(external_order_id__isnull=False),
            ),
            models.UniqueConstraint(
                fields=["provider", "external_payment_id"],
                name="payment_external_payment_once_per_provider",
                condition=models.Q(external_payment_id__isnull=False),
            ),
            models.CheckConstraint(condition=models.Q(amount__gt=0), name="payment_amount_positive"),
        ]
        ordering = ["-created_at"]

    def _subject_identity_unchanged(self):
        """True when this is a saved row still pointing at the same subject and member.

        A missing subject is legitimate for a payment whose subject was purged, but only if
        nothing about who owes what has been edited. Skipping validation merely because `pk`
        exists would be too broad -- it would let an existing row be repointed at a foreign
        subject. New rows always validate.
        """
        if self._state.adding or not self.pk:
            return False
        return (
            type(self)
            .objects.filter(
                pk=self.pk,
                makerspace_id=self.makerspace_id,
                subject_type=self.subject_type,
                subject_id=self.subject_id,
                member_id=self.member_id,
            )
            .exists()
        )

    def clean(self):
        self.currency = (self.currency or "").lower()
        currency_validator(self.currency)
        subject_identity_unchanged = self._subject_identity_unchanged()
        from apps.payments.subject_validation import validate_subject

        validate_subject(self, subject_identity_unchanged)

    def save(self, *args, **kwargs):
        if self.pk:
            original = type(self).objects.filter(pk=self.pk).values(
                "status", "amount", "provider", "stripe_provider", "stripe_connected_account_id", "stripe_application_fee_amount", "online_rail", "due_at",
                "tax_snapshot", "method_label", "pricing_snapshot",
            ).first()
            if original and original["tax_snapshot"] != self.tax_snapshot:
                raise ValidationError(gettext("A charge's tax snapshot is immutable."))
            if original and original["pricing_snapshot"] != self.pricing_snapshot:
                raise ValidationError(gettext("A charge's pricing snapshot is immutable."))
            if original and original["method_label"] and original["method_label"] != self.method_label:
                raise ValidationError(gettext("A payment method label is set once."))
            if original and original["due_at"] != self.due_at:
                raise ValidationError(gettext("A charge due date is immutable."))
            if original and original["status"] != self.Status.PENDING and (
                original["status"] != self.status or original["amount"] != self.amount
            ):
                raise ValidationError(gettext("Terminal payments are immutable."))
            # A charge raised with no gateway configured carries `provider=unclaimed`:
            # it has no provenance yet, so the first checkout that reaches a provider is
            # allowed to stamp one, exactly once. Without this exemption the guard below
            # rejected that stamp and an unclaimed debt could NEVER be claimed, even
            # after valid credentials were added -- the database trigger permitting the
            # transition was never reached.
            claiming = (
                original
                and original["provider"] == self.Provider.UNCLAIMED
                and self.provider != self.Provider.UNCLAIMED
            )
            if not claiming and original and any(
                original[field] != getattr(self, field)
                for field in ("provider", "stripe_provider", "stripe_connected_account_id", "stripe_application_fee_amount")
            ):
                # `provider` joins the provenance set: moving a charge between vendors
                # would point the row at a merchant account that never took the money,
                # and every settlement and refund path after it would be wrong.
                raise ValidationError(gettext("Payment provenance is immutable."))
            if (
                original
                and original['online_rail'] is not None
                and original['online_rail'] != self.online_rail
            ):
                raise ValidationError(gettext('The online payment rail is immutable once claimed.'))
        self.full_clean()
        return super().save(*args, **kwargs)


class ProcessedStripeEvent(models.Model):
    """Webhook idempotency, for every provider.

    Kept under its original name and table: renaming a model whose rows are the only
    defence against double-settling a real charge is a migration risk with no payoff.
    The `provider` column is what generalises it -- two vendors can emit the same event
    id, and without it the second one would be silently swallowed as a duplicate.
    """

    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.PROTECT, related_name="processed_stripe_events")
    provider = models.CharField(max_length=16, default=Payment.Provider.STRIPE)
    stripe_event_id = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["makerspace", "provider", "stripe_event_id"],
                name="webhook_event_once_per_makerspace_provider",
            )
        ]
