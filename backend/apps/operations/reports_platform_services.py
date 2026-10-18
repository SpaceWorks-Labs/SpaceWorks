"""Platform provider metering. The only permitted hidden-tenant projection lives here."""

from datetime import timezone as datetime_timezone

from django.db.models import Case, CharField, Count, F, Q, Value, When
from django.db.models.functions import TruncDay

from apps.accounts.models_activity import AttestationVerificationLog
from apps.backup.models import BackupArchive, BackupRun
from apps.backup.models_runs import BackupRunCoverage
from apps.integrations.models import EmailLog, NotificationDeliveryLog
from apps.integrations.models_tracking import SmsSendLog
from apps.operations.reports_notification_facts import canonical_deliveries, delivery_facts
from apps.operations.reports_push_facts import push_querysets
from apps.operations.platform_scope import hidden_platform_service_bucket, platform_analytics_spaces, require_platform_context
from apps.operations.report_types import ReportNotFound, ReportResult
from apps.operations.reports_common import apply_range, limited
from apps.operations.reports_j_common import calendar_range, period
from apps.operations.reports_finance_sources import finance_sources
from apps.payments.models import Payment
from apps.operations.report_fields_j import SERVICES_FIELDS as FIELDS



def _outcomes(qs, service, *, scope="makerspace_id", outcome="status", provider="provider_source", date_range=None, purpose=None):
    qs = apply_range(qs, "created_at", date_range)
    aliases = {"day": TruncDay("created_at", tzinfo=datetime_timezone.utc)}
    if scope != "makerspace_id":
        aliases["makerspace_id"] = F(scope)
    aliases["_analytics_outcome"] = F(outcome)
    qs = qs.order_by().annotate(**aliases)
    fields = ["makerspace_id", "day", "_analytics_outcome"]
    if provider:
        fields.append(provider)
    for row in qs.values(*fields).annotate(count=Count("pk")):
        source = row.get(provider) if provider else "platform"
        status = row["_analytics_outcome"]
        yield {"makerspace_id": row["makerspace_id"], "day": row["day"].date(),
               "service": service, "status": status if status in ("pending", "sending", "accepted", "sent", "delivered", "read", "failed", "skipped", "suppressed", "held") else "unknown", "count": row["count"],
               **({"purpose": purpose} if purpose else {}),
               "provider_source": source if source in ("platform", "own") else "unknown"}


def _payment_rows(visible_ids, hidden_ids, date_range, *, provider="connect"):
    # Use the dated finance seam for settlement/refund correction heads. No
    # payment handle, payer, receipt text or provider-attempt failure is exposed.
    ids = visible_ids | hidden_ids
    payments = Payment.objects.filter(makerspace_id__in=ids, stripe_provider=provider).exclude(provider="unclaimed")
    if provider == "connect":
        payments = payments.filter(provider="stripe")
    attributed = dict(payments.values_list("pk", "makerspace_id"))
    for space_id in sorted(set(attributed.values())):
        for _space, row in finance_sources(space_id, date_range=date_range):
            kind = row["row_kind"]
            if row["payment_id"] not in attributed or not row["effective"]:
                continue
            if kind == "refund" and row.get("refund_status") != "succeeded":
                continue
            if kind not in ("charge", "online_settlement", "manual_settlement", "legacy_settlement", "refund"):
                continue
            yield {"makerspace_id": space_id, "day": row["date"].astimezone(datetime_timezone.utc).date(),
                   "service": "connect" if provider == "connect" else "payments", "provider_source": "platform" if provider == "connect" else "own", "status": kind,
                   "count": 1, **({"currency": row["currency"], "amount": row["amount"]} if provider == "connect" else {})}


def build_platform_services(makerspace_id=None, *, platform_context=None, limit=None, date_range=None, grain="day"):
    ctx = require_platform_context(platform_context)
    date_range = calendar_range(date_range)
    if makerspace_id is not None:
        raise ReportNotFound()
    from apps.makerspaces.models import Makerspace
    visible = set(platform_analytics_spaces(ctx).values_list("pk", flat=True))
    hidden = set(Makerspace.objects.filter(superadmin_access_enabled=False).values_list("pk", flat=True))
    permitted = Q(makerspace_id__in=visible | hidden) | Q(makerspace_id__isnull=True)
    email = EmailLog.objects.filter(permitted).annotate(analytics_status=Case(
        When(status="skipped", error="email_address_suppressed", then=Value("suppressed")),
        default=F("status"), output_field=CharField(),
    ))
    raw = list(_outcomes(email, "email", outcome="analytics_status", date_range=date_range))
    raw.extend(_outcomes(SmsSendLog.objects.filter(permitted), "sms", date_range=date_range, purpose="otp"))
    personal = apply_range(canonical_deliveries().filter(makerspace_id__in=visible | hidden).exclude(
        channel__in=("email", "native_push", "in_app")), "created_at", date_range)
    for fact in delivery_facts(personal):
        channel = fact["channel"]
        if channel not in ("sms", "whatsapp", "telegram", "slack", "mattermost", "discord", "webhook"):
            continue
        raw.append({"makerspace_id": fact["makerspace_id"],
            "day": fact["created_at"].astimezone(datetime_timezone.utc).date(), "service": channel,
            "status": fact["status"], "provider_source": fact["provider_source"]
                if fact["provider_source"] in ("own", "platform") else "unknown", "count": 1,
            **({"purpose": "notifications"} if channel in ("sms", "whatsapp") else {})})
    for qs, tenant, _feature, _audience in push_querysets(visible | hidden):
        raw.extend(_outcomes(qs, "push", scope=tenant, date_range=date_range))
    # Chat providers are tenant-owned; the parent delivery log is never counted
    # again for native push, whose authority is the per-device outcome ledger.
    chat = NotificationDeliveryLog.objects.filter(makerspace_id__in=visible).exclude(channel="native_push")
    for channel in ("telegram", "slack", "mattermost", "discord", "webhook"):
        raw.extend({**r, "provider_source": "own"} for r in _outcomes(chat.filter(channel=channel), channel, provider=None, date_range=date_range))
    attestation = apply_range(AttestationVerificationLog.objects.all(), "created_at", date_range)
    for row in attestation.order_by().annotate(day=TruncDay("created_at", tzinfo=datetime_timezone.utc)).values("day", "outcome").annotate(count=Count("pk")):
        raw.append({"makerspace_id": None, "day": row["day"].date(), "service": "attestation",
                    "status": row["outcome"], "provider_source": "platform", "count": row["count"]})
    # Coverage is one service operation per run/tenant, including tenants packed
    # into a global archive. Global run health is a separate deployment row.
    coverage = apply_range(BackupRunCoverage.objects.filter(makerspace_id_snapshot__in=visible | hidden), "run__started_at", date_range)
    for row in coverage.values("makerspace_id_snapshot", "run__started_at", "run__status", "state"):
        raw.append({"makerspace_id": row["makerspace_id_snapshot"], "day": row["run__started_at"].astimezone(datetime_timezone.utc).date(),
                    "service": "backups", "provider_source": "platform", "count": 1,
                    "status": "sent" if row["state"] == "covered" else "failed" if row["run__status"] == "failed" else "pending"})
    for run in apply_range(BackupRun.objects.filter(coverage_rows__isnull=True), "started_at", date_range).values("started_at", "status"):
        raw.append({"makerspace_id": None, "day": run["started_at"].astimezone(datetime_timezone.utc).date(),
                    "service": "backups", "provider_source": "platform", "count": 1,
                    "status": {"complete": "sent", "failed": "failed"}.get(run["status"], "pending")})
    standalone = apply_range(BackupArchive.objects.filter(backup_run__isnull=True), "created_at", date_range)
    for archive in standalone.values("makerspace_id", "created_at", "status"):
        if archive["makerspace_id"] not in visible | hidden and archive["makerspace_id"] is not None:
            continue
        raw.append({"makerspace_id": archive["makerspace_id"], "day": archive["created_at"].astimezone(datetime_timezone.utc).date(),
                    "service": "backups", "provider_source": "platform", "count": 1,
                    "status": "sent" if archive["status"] in ("available", "expired") else "failed" if archive["status"] == "failed" else "pending"})
    raw.extend(_payment_rows(visible, hidden, date_range))
    raw.extend(_payment_rows(visible, set(), date_range, provider="raw"))
    records = hidden_platform_service_bucket(ctx, raw, report_key="platform-services")
    groups = {}
    for row in raw:
        if row["makerspace_id"] not in visible and row["makerspace_id"] is not None:
            continue
        at = row["day"]
        from datetime import datetime, time
        bucket = period(datetime.combine(at, time.min, tzinfo=datetime_timezone.utc), grain)
        key = (row["makerspace_id"], bucket, row["service"], row["provider_source"], row["status"], row.get("currency"), row.get("purpose"))
        state = groups.setdefault(key, {**row, "period": bucket, "day": bucket, "bucket": "makerspace" if row["makerspace_id"] else "deployment", "count": 0, "amount": None})
        state["count"] += row["count"]
        if "amount" in row:
            state["amount"] = (state["amount"] or 0) + row["amount"]
    records.extend(groups.values())
    records.sort(key=lambda r: (r.get("period") or r.get("day"), r["service"], r.get("makerspace_id") or 0, r.get("status", ""), r.get("currency") or ""))
    return ReportResult(FIELDS, limited(records, limit), {"limitations": "UTC cohorts; Connect offers attributed charge/settlement/successful refund counts and currency amounts, without provider-attempt failure history. Hidden service counts stay daily. Empty provider history is unknown. Backups count tenant coverage once; standalone runs/archives have no duplicate coverage."})
