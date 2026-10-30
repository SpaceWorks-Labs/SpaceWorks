"""Platform-only aggregates. No roster, message content or credential field is read."""

from datetime import UTC, datetime, time, timedelta

from django.db.models import Count, Min, Q
from django.db.models.functions import TruncDate
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.admin_api.permissions import IsActiveSuperAdmin, active_user
from apps.integrations.models_contract import NotificationDelivery, NotificationEnvelope
from apps.integrations.models_email import EmailLog
from apps.makerspaces.models import Makerspace
from apps.makerspaces.servability import servable_queryset


def require_platform(actor):
    if (not active_user(actor) or actor.account_kind != "platform"
            or not (actor.is_superuser or actor.role == User.Role.SUPERADMIN)):
        raise PermissionDenied()


def _daily(rows, field, start, end):
    values = rows.filter(**{f"{field}__gte": start, f"{field}__lt": end}).annotate(
        day=TruncDate(field, tzinfo=UTC)).values("day").annotate(n=Count("pk", distinct=True))
    return {value["day"]: value["n"] for value in values}


def _health(kind, rows, *, pending, failed):
    values = rows.aggregate(pending=Count("pk", filter=pending),
                            failed=Count("pk", filter=failed),
                            oldest_pending_at=Min("created_at", filter=pending))
    return {"kind": kind, **values}


def _organization_insights(spaces):
    """Cross-event organisation rows (R2 L2, G8); counts under k=10 are suppressed."""
    from apps.separability.registry import runtime_active
    if not runtime_active("events"):
        return []
    from apps.events.programme.analytics_org import organization_insights
    return organization_insights(spaces)


def platform_insights(actor, *, days=30, now=None):
    require_platform(actor)
    if type(days) is not int or not 1 <= days <= 30:
        raise ValidationError({"days": "Choose a window from 1 to 30 days."})
    now = now or timezone.now()
    first = now.astimezone(UTC).date() - timedelta(days=days - 1)
    start = datetime.combine(first, time.min, tzinfo=UTC)
    spaces = servable_queryset(Makerspace.objects.all())
    accounts = User.objects.filter(is_tenant_dump_stub=False, is_walk_in=False)
    account_growth = _daily(accounts, "date_joined", start, now)
    tenant_growth = _daily(spaces, "created_at", start, now)
    staff = accounts.filter(account_kind="staff", is_active=True, access_status="active",
                            staff_makerspace__in=spaces)
    active = staff.count()
    enabled = staff.filter(usermfa__enabled_at__isnull=False).exclude(usermfa__secret="").count()
    email = EmailLog.objects.filter(Q(makerspace__in=spaces) | Q(makerspace__isnull=True))
    envelopes = NotificationEnvelope.objects.filter(makerspace__in=spaces)
    deliveries = NotificationDelivery.objects.filter(makerspace__in=spaces)
    growth = [{"date": (first + timedelta(days=index)).isoformat(),
               "accounts": account_growth.get(first + timedelta(days=index), 0),
               "makerspaces": tenant_growth.get(first + timedelta(days=index), 0)} for index in range(days)]
    return {"window": {"starts_at": start, "ends_at": now}, "growth": growth,
            "organizations": _organization_insights(spaces),
            "staff_mfa": {"active": active, "enabled": enabled, "without_mfa": active - enabled,
                          "adoption_percent": round(enabled * 100 / active, 2) if active else None},
            "outbox": [
                _health("email", email, pending=Q(status__in=("pending", "sending")), failed=Q(status="failed")),
                _health("personal_envelope", envelopes, pending=Q(processed_at__isnull=True), failed=Q(pk__in=[])),
                _health("personal_delivery", deliveries, pending=Q(state="retrying"), failed=Q(state="failed")),
            ]}


class WindowSerializer(serializers.Serializer):
    starts_at = serializers.DateTimeField()
    ends_at = serializers.DateTimeField()


class GrowthSerializer(serializers.Serializer):
    date = serializers.DateField()
    accounts = serializers.IntegerField(min_value=0)
    makerspaces = serializers.IntegerField(min_value=0)


class MfaSerializer(serializers.Serializer):
    active = serializers.IntegerField(min_value=0)
    enabled = serializers.IntegerField(min_value=0)
    without_mfa = serializers.IntegerField(min_value=0)
    adoption_percent = serializers.FloatField(allow_null=True)


class OutboxHealthSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=("email", "personal_envelope", "personal_delivery"))
    pending = serializers.IntegerField(min_value=0)
    failed = serializers.IntegerField(min_value=0)
    oldest_pending_at = serializers.DateTimeField(allow_null=True)


class OrganizationInsightSerializer(serializers.Serializer):
    organization_id = serializers.IntegerField()
    name = serializers.CharField()
    events = serializers.IntegerField(min_value=0)
    registrations = serializers.IntegerField(min_value=0, allow_null=True)
    attended = serializers.IntegerField(min_value=0, allow_null=True)
    attendance_percent = serializers.FloatField(allow_null=True)
    suppressed = serializers.BooleanField(help_text="True when a count is under 10 and is withheld.")


class PlatformInsightsSerializer(serializers.Serializer):
    window = WindowSerializer()
    growth = GrowthSerializer(many=True)
    organizations = OrganizationInsightSerializer(many=True)
    staff_mfa = MfaSerializer()
    outbox = OutboxHealthSerializer(many=True)


class InsightsError(serializers.Serializer):
    detail = serializers.CharField()


class PlatformInsightsView(APIView):
    permission_classes = [IsActiveSuperAdmin]

    @extend_schema(tags=["Platform insights"], request=None,
                   parameters=[OpenApiParameter("days", int, description="1–30 UTC days, default 30.")],
                   responses={200: PlatformInsightsSerializer,
                              **{code: InsightsError for code in (400, 401, 403, 429)}})
    def get(self, request):
        if set(request.query_params) - {"days"}:
            raise ValidationError("Unknown query parameter.")
        raw = request.query_params.get("days", "30")
        if len(raw) > 2 or not raw.isascii() or not raw.isdecimal():
            raise ValidationError({"days": "Choose a window from 1 to 30 days."})
        data = platform_insights(request.user, days=int(raw))
        return Response(PlatformInsightsSerializer(data).data, headers={"Cache-Control": "private, no-store"})
