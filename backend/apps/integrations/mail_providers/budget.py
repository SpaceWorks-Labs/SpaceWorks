"""Short DB transactions serialize account-wide reservations, never provider I/O.

Models are supplied by the integration lane: operations.CloudEmailBudgetAccount
and operations.CloudEmailReservation. Missing tables/configuration fail closed.
"""

from datetime import datetime, time, timedelta
from contextlib import contextmanager
from zoneinfo import ZoneInfo

from django.apps import apps
from django.db import transaction, connection
from django.db.models import Q, Sum
from django.utils import timezone

from apps.audit import services as audit

CHARGED = ("reserved", "accepted", "uncertain")


def window_rows(rows, *, day=None, month=None):
    # A send reserved before reset may be accepted after it. Pending/uncertain
    # requests carry forward until reconciled; accepted sends charge both windows.
    field, value = ("day", day) if day is not None else ("month", month)
    return rows.filter(Q(state__in=("reserved", "uncertain")) |
                       Q(state="accepted", **{field: value}) |
                       Q(state="accepted", **{f"accepted_{field}": value}))


class BudgetDeferred(Exception):
    def __init__(self, code, retry_at=None):
        self.code, self.retry_at = code, retry_at
        super().__init__(code)


def models():
    return (apps.get_model("operations", "CloudEmailBudgetAccount"),
            apps.get_model("operations", "CloudEmailReservation"))


@contextmanager
def bound_transaction(*, settlement=False):
    # Only called by free reservation paths, after entering their short atomic block.
    from .delivery import delivery_timeout
    milliseconds = 1000 if settlement else max(1, int(min(delivery_timeout(), 2) * 1000))
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_setting('lock_timeout'), current_setting('statement_timeout')")
        previous = cursor.fetchone()
        cursor.execute("SELECT set_config('lock_timeout', %s, true), set_config('statement_timeout', %s, true)",
                       [str(milliseconds), str(milliseconds)])
    try:
        yield
    finally:
        if not connection.needs_rollback:
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('lock_timeout', %s, true), set_config('statement_timeout', %s, true)", previous)


def reset_at(now, zone, *, monthly=False):
    local = now.astimezone(ZoneInfo(zone))
    day = local.date() + timedelta(days=1)
    if monthly:
        day = (local.date().replace(day=28) + timedelta(days=4)).replace(day=1)
    return datetime.combine(day, time.min, ZoneInfo(zone))


def reserve(account, *, log, attempt_key, recipients, now=None):
    if type(recipients) is not int or not 1 <= recipients <= 1000:
        raise ValueError("Invalid mail recipient count.")
    if not isinstance(attempt_key, str) or not 1 <= len(attempt_key) <= 200:
        raise ValueError("Invalid mail attempt key.")
    now = now or timezone.now()
    local = now.astimezone(ZoneInfo(account.reset_timezone))
    Account, Reservation = models()
    with transaction.atomic(), bound_transaction():
        from apps.encryption.write_fence import assert_mapped_write_allowed
        assert_mapped_write_allowed(log.makerspace_id)
        row, _ = Account.objects.get_or_create(key=account.key, defaults={
            "provider": account.provider, "reset_timezone": account.reset_timezone})
        # This is intentionally deployment/account scoped, not a per-tenant allowance.
        row = Account.objects.select_for_update().get(pk=row.pk)
        if row.provider != account.provider or row.reset_timezone != account.reset_timezone:
            raise BudgetDeferred("email_budget_account_policy_changed")
        existing = Reservation.objects.filter(attempt_key=attempt_key).first()
        if existing:
            if existing.account_id != row.pk or existing.recipients != recipients:
                raise BudgetDeferred("email_budget_identity_mismatch")
            if existing.state == "accepted":
                return existing
            if existing.state != "released":
                raise BudgetDeferred("email_acceptance_uncertain")
        charged = Reservation.objects.filter(account=row, state__in=CHARGED)
        daily = window_rows(charged, day=local.date()).aggregate(total=Sum("recipients"))["total"] or 0
        monthly = window_rows(charged, month=local.date().replace(day=1)).aggregate(total=Sum("recipients"))["total"] or 0
        if account.monthly_cap is not None and monthly + recipients > account.monthly_cap:
            raise BudgetDeferred("email_monthly_budget_reached", reset_at(now, account.reset_timezone, monthly=True))
        if daily + recipients > account.daily_cap:
            raise BudgetDeferred("email_daily_budget_reached", reset_at(now, account.reset_timezone))
        values = dict(account=row, provider=account.provider, day=local.date(),
                      month=local.date().replace(day=1), recipients=recipients,
                      state="reserved", log_id=log.pk)
        if existing:
            for name, value in values.items():
                setattr(existing, name, value)
            existing.save(update_fields=[*values, "updated_at"])
            receipt = existing
        else:
            receipt = Reservation.objects.create(attempt_key=attempt_key, **values)
        audit.record(None, "email.budget_reserved", makerspace=log.makerspace,
                     target=log, meta={"reservation_id": str(receipt.pk), "recipients": recipients})
        return receipt


def settle(receipt, state, *, log, now=None, provider_message_id=""):
    if state not in {"accepted", "uncertain", "released"}:
        raise ValueError("Invalid mail reservation outcome.")
    Account, Reservation = models()
    with transaction.atomic(), bound_transaction(settlement=True):
        # Settlement must preserve an accepted/uncertain result even at deadline.
        from apps.encryption.write_fence import assert_mapped_write_allowed
        assert_mapped_write_allowed(log.makerspace_id)
        account = Account.objects.select_for_update().get(pk=receipt.account_id)
        locked = Reservation.objects.select_for_update().get(pk=receipt.pk)
        if locked.state != "reserved":
            return  # Monotonic: a duplicate result cannot release an accepted send.
        locked.state = state
        if state == "accepted":
            accepted = (now or timezone.now()).astimezone(ZoneInfo(account.reset_timezone)).date()
            locked.accepted_day, locked.accepted_month = accepted, accepted.replace(day=1)
            locked.provider_message_id = provider_message_id[:200] if isinstance(provider_message_id, str) else ""
        locked.save(update_fields=["state", "accepted_day", "accepted_month", "provider_message_id", "updated_at"])
        audit.record(None, "email.budget_settled", makerspace=log.makerspace,
                     target=log, meta={"reservation_id": str(receipt.pk), "outcome": state})


def usage(account, *, now=None):
    """Internal facts only. I scopes/sanitizes health responses for tenant staff."""
    _, Reservation = models()
    now = now or timezone.now()
    day = now.astimezone(ZoneInfo(account.reset_timezone)).date()
    all_rows = Reservation.objects.filter(account__key=account.key, state__in=CHARGED)
    rows = window_rows(all_rows, day=day)
    result = {state: 0 for state in CHARGED}
    for row in rows.values("state").annotate(total=Sum("recipients")):
        result[row["state"]] = row["total"]
    monthly = window_rows(all_rows, month=day.replace(day=1)).aggregate(total=Sum("recipients"))["total"] or 0
    return {**result, "daily_cap": account.daily_cap, "monthly_cap": account.monthly_cap,
            "monthly_charged": monthly, "sampled_at": now, "provider_usage_known": False,
            "reset_at": reset_at(now, account.reset_timezone), "scope": "application_account"}
