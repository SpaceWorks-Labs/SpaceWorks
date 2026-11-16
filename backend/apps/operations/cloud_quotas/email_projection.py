"""Recipient accounting contains no mailbox, account credential or provider ID."""
from datetime import datetime
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db.models import Sum
from django.utils import timezone

from apps.integrations.mail_providers.budget import window_rows
from apps.operations.models import CloudEmailBudgetAccount, CloudEmailReservation


def email_accounts(*, makerspace=None):
    result = []
    accounts = CloudEmailBudgetAccount.objects.all()
    if makerspace is not None:
        owned = CloudEmailReservation.objects.filter(log__makerspace=makerspace).values("account_id")
        accounts = accounts.filter(pk__in=owned)
    for index, account in enumerate(accounts.order_by("pk")[:100]):
        day = timezone.now().astimezone(ZoneInfo(account.reset_timezone)).date()
        rows = CloudEmailReservation.objects.filter(account=account)
        if makerspace is not None:
            rows = rows.filter(log__makerspace=makerspace)
        daily = window_rows(rows, day=day)
        counts = {state: daily.filter(state=state).aggregate(n=Sum("recipients"))["n"] or 0
                  for state in ("accepted", "reserved", "uncertain")}
        policy = getattr(settings, "FREE_EMAIL_ACCOUNTS", {}).get(account.key, {})
        if account.key == getattr(settings, "FREE_EMAIL_ACCOUNT_KEY", "") and not policy:
            policy = {"daily_cap": getattr(settings, "FREE_EMAIL_DAILY_CAP", None),
                      "monthly_cap": getattr(settings, "FREE_EMAIL_MONTHLY_CAP", None)}
        monthly = window_rows(rows, month=day.replace(day=1)).exclude(state="released")
        result.append({"label": f"Email account {index + 1}" if makerspace is None else "Your email usage",
            "provider": account.provider, **counts, "daily_cap": policy.get("daily_cap") if makerspace is None else None,
            "monthly_cap": policy.get("monthly_cap") if makerspace is None else None,
            "monthly_charged": monthly.aggregate(n=Sum("recipients"))["n"] or 0,
            "reset_timezone": account.reset_timezone, "provider_usage_known": False})
    return result
