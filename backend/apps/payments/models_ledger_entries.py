"""The space's finance ledger rows for money that is not a member charge (#94, #100).

A `LedgerEntry` is money the space spent (a To-Buy purchase, a repair payout, rent) or
received outside a `Payment` (a donation, a grant, a sponsorship). Member charges stay
`Payment` rows, refunds stay `Refund` rows and event payouts stay `EventPayoutEntry` rows;
the income-versus-spending report reads all of them, so nothing is recorded twice.

Every row carries the `domain` (and `machine_type` where it applies) that decides who may
see it (#100), and the `source_kind`/`source_id` of whatever caused it, so a lane calling
`ledger_api.record_expense` twice for the same purchase gets the same row back.

Entries are append-only: a mistake is VOIDED with a reason (the row stays, marked void,
and drops out of the totals), never edited or deleted. `OpeningBalance` rows are
append-only revisions; the newest row for a (financial year, currency) is the balance.
"""

from django.utils.translation import gettext, gettext_noop
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models

from apps.payments.models_settings import currency_validator
from apps.payments.money_model import MoneyDecimalField

slug_validator = RegexValidator(r"^[a-z][a-z0-9_.]{0,47}$", "Use lower-case letters, digits, '_' or '.'.")


class LedgerEntry(models.Model):
    class Kind(models.TextChoices):
        RECEIPT = "receipt", gettext_noop("Money in")
        EXPENSE = "expense", gettext_noop("Money out")

    class Domain(models.TextChoices):
        INVENTORY = "inventory", "Inventory"
        LOANS = "loans", "Inventory loans"
        MACHINES = "machines", "Machines"
        BOOKINGS = "bookings", gettext_noop("Bookings and rooms")
        EVENTS = "events", "Events"
        MEMBERSHIP = "membership", "Membership"
        DONATIONS = "donations", gettext_noop("Donations and sponsors")
        SHOP = "shop", "Shop"
        GENERAL = "general", "General"

    class Method(models.TextChoices):
        CASH = "cash", "Cash"
        UPI = "upi", "UPI"
        BANK_TRANSFER = "bank_transfer", gettext_noop("Bank transfer")
        CARD = "card", "Card"
        CHEQUE = "cheque", "Cheque"
        ONLINE = "online", "Online"
        OTHER = "other", "Other"

    class Account(models.TextChoices):
        CASH = "cash", "Cash"
        BANK = "bank", "Bank"

    RECEIPT_CATEGORIES = ("donation", "grant", "sponsorship", "interest", "venue_fee", "other_income")
    EXPENSE_CATEGORIES = ("to_buy", "repair", "maintenance", "consumables", "reimbursement", "prize", "rent",
                          "utilities", "equipment", "salaries", "software", "events", "other_expense")

    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="ledger_entries")
    kind = models.CharField(max_length=16, choices=Kind.choices)
    domain = models.CharField(max_length=16, choices=Domain.choices)
    # SET_NULL keeps the money when a type is retired; the label snapshot keeps it readable.
    machine_type = models.ForeignKey("machines.MachineType", null=True, blank=True, on_delete=models.SET_NULL,
                                     related_name="+")
    machine_type_label = models.CharField(max_length=120, blank=True, default="")
    event = models.ForeignKey("events.Event", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    category = models.CharField(max_length=48, validators=[slug_validator])
    method = models.CharField(max_length=16, choices=Method.choices)
    account = models.CharField(max_length=8, choices=Account.choices)
    amount = MoneyDecimalField(max_digits=13, decimal_places=3)
    currency = models.CharField(max_length=3, validators=[currency_validator])
    entry_date = models.DateField()
    description = models.CharField(max_length=300)
    #: Who was paid or who paid, as staff write it (a supplier, a funder). Business data.
    counterparty = models.CharField(max_length=150, blank=True, default="")
    reference = models.CharField(max_length=64, blank=True, default="")
    #: What caused the row (`manual`, `procurement.to_buy`, `repairs.payout`, ...) and its id.
    source_kind = models.CharField(max_length=48, validators=[slug_validator], default="manual")
    source_id = models.CharField(max_length=64, blank=True, default="")
    receipt = models.ForeignKey("evidence.EvidencePhoto", null=True, blank=True, on_delete=models.PROTECT,
                                related_name="+")
    created_by = models.ForeignKey("accounts.User", null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    voided_at = models.DateTimeField(null=True, blank=True)
    voided_by = models.ForeignKey("accounts.User", null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    void_reason = models.CharField(max_length=300, blank=True, default="")

    class Meta:
        ordering = ["-entry_date", "-pk"]
        constraints = [
            models.CheckConstraint(condition=models.Q(amount__gt=0), name="ledger_entry_amount_positive"),
            models.CheckConstraint(condition=models.Q(voided_at__isnull=True, void_reason="") | models.Q(
                voided_at__isnull=False) & ~models.Q(void_reason=""), name="ledger_entry_void_shape"),
            models.CheckConstraint(condition=models.Q(machine_type__isnull=True) | models.Q(domain="machines"),
                                   name="ledger_entry_machine_type_domain"),
            models.UniqueConstraint(fields=["makerspace", "kind", "source_kind", "source_id"],
                                    condition=models.Q(voided_at__isnull=True) & ~models.Q(source_id=""),
                                    name="ledger_entry_source_once"),
            models.UniqueConstraint(fields=["receipt"], name="ledger_entry_receipt_once"),
        ]
        indexes = [models.Index(fields=["makerspace", "entry_date"], name="ledger_entry_space_date_idx"),
                   models.Index(fields=["makerspace", "domain"], name="ledger_entry_space_domain_idx")]

    def clean(self):
        allowed = self.RECEIPT_CATEGORIES if self.kind == self.Kind.RECEIPT else self.EXPENSE_CATEGORIES
        if self.source_kind == "manual" and self.category not in allowed:
            raise ValidationError({"category": gettext("Choose a category for this kind of entry.")})

    def save(self, *args, **kwargs):
        if self.pk:
            original = type(self).objects.filter(pk=self.pk).values("voided_at").first()
            if original and original["voided_at"] is not None:
                raise ValidationError(gettext("A voided ledger entry is final."))
        else:
            self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError(gettext("Ledger entries are voided, never deleted."))


class OpeningBalance(models.Model):
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="+")
    fy_start = models.DateField()
    currency = models.CharField(max_length=3, validators=[currency_validator])
    cash_amount = MoneyDecimalField(max_digits=13, decimal_places=3, default=0)
    bank_amount = MoneyDecimalField(max_digits=13, decimal_places=3, default=0)
    set_by = models.ForeignKey("accounts.User", on_delete=models.PROTECT, related_name="+")
    set_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-set_at", "-pk"]
        indexes = [models.Index(fields=["makerspace", "fy_start", "currency"], name="opening_balance_lookup_idx")]

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError(gettext("Opening balances are revised by appending a new row."))
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError(gettext("Opening balances are revised by appending a new row."))
