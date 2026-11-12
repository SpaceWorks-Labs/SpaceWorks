"""Counters for the decision-284 resource keys (``extra_quotas``); one small function per key.

Every counter reads rows that already exist (no new table, no migration). Monthly counters use the
UTC calendar month and count cancelled or deleted-by-status rows too, so churning cannot reset a
quota (the same rule as ``space_quotas``); total counters count only the rows that still "exist".
"""
from datetime import UTC, datetime

from django.db.models import Sum


def month_start():
    now = datetime.now(UTC)
    return datetime(now.year, now.month, 1, tzinfo=UTC)


def event_registrations_monthly(space):
    """Registrations created this month plus unclaimed ticket seats that are not registrations yet.

    A claimed seat becomes an ``EventRegistration`` and is counted there, so nothing counts twice.
    """
    from apps.events.models_orders import EventOrderSeat
    from apps.events.models_registration import EventRegistration
    start = month_start()
    seats = EventOrderSeat.objects.filter(makerspace=space, created_at__gte=start, registration__isnull=True
                                          ).exclude(status=EventOrderSeat.Status.VOID).count()
    return EventRegistration.objects.filter(event__makerspace=space, created_at__gte=start).count() + seats


def shop_orders_monthly(space):
    from apps.shop.models_orders import ShopOrder
    return ShopOrder.objects.filter(makerspace=space, created_at__gte=month_start()).count()


def shop_products(space):
    from apps.shop.models_catalogue import ShopProduct
    return ShopProduct.objects.filter(makerspace=space, archived_at__isnull=True).count()


def membership_plans(space):
    from apps.makerspaces.models_membership_plans import MembershipPlan
    return MembershipPlan.objects.filter(makerspace=space, archived_at__isnull=True).count()


def member_units(space):
    from apps.makerspaces.models_member_units import MemberUnit
    return MemberUnit.objects.filter(makerspace=space, archived_at__isnull=True).count()


def donation_campaigns(space):
    from apps.payments.donations.models_donations import DonationCampaign
    return DonationCampaign.objects.filter(makerspace=space, is_active=True).count()


def bookable_spaces(space):
    from apps.bookings.models_spaces import BookableSpace
    return BookableSpace.objects.filter(makerspace=space, is_active=True).count()


def boxes(space):
    from apps.boxes.models import Box
    return Box.objects.filter(makerspace=space, is_active=True).count()


def organizations_linked(space):
    from apps.organizations.models import OrganizationMakerspace
    return OrganizationMakerspace.objects.filter(makerspace=space).count()


def analytics_connections(space):
    """Configured providers on the space's one analytics row: Metabase and Grafana count one each."""
    from apps.analytics.models import AnalyticsConnection
    row = AnalyticsConnection.objects.filter(makerspace=space).first()
    return 0 if row is None else bool(row.metabase_url) + bool(row.grafana_url)


def webhook_endpoints(space):
    """Configured outbound webhook destinations (the `webhook` channel), active or not."""
    from apps.integrations.models_destinations import NotificationDestination
    return NotificationDestination.objects.filter(makerspace=space, channel="webhook").count()


def report_exports_monthly(space):
    """Report-registry downloads (CSV/XLSX/PDF) this month, read from the append-only audit trail."""
    from apps.audit.models import AuditLog
    return AuditLog.objects.filter(action="report.downloaded", makerspace=space, created_at__gte=month_start()).count()


def collection_sheet_rows_monthly(space):
    """Rows submitted on collection sheets this month, summed from the append-only audit trail (no new table)."""
    from apps.audit.models import AuditLog
    rows = AuditLog.objects.filter(action="payment.collection_sheet_recorded", makerspace=space,
                                   created_at__gte=month_start()).values_list("meta", flat=True)
    return sum(int((meta or {}).get("rows") or 0) for meta in rows)


def kiosk_stations(space):
    from apps.makerspaces.models_stations import Station
    return Station.objects.filter(makerspace=space, kind__in=(Station.Kind.SCANNER, Station.Kind.HANDOVER)).count()


def paired_displays(space):
    from apps.presence.models_display import DisplayScreen
    return DisplayScreen.objects.filter(makerspace=space, revoked_at__isnull=True).count()


def adapter_bridges(space):
    from apps.devices.models import Device
    return Device.objects.filter(makerspace=space, kind=Device.Kind.ADAPTER).exclude(status=Device.Status.REVOKED).count()


def adapter_watch_streams(space):
    from django.utils import timezone
    from apps.devices.models import AdapterWatch
    return AdapterWatch.objects.filter(makerspace=space, status="active", expires_at__gt=timezone.now()).count()


def adapter_snapshots(space):
    from apps.devices.models import AdapterCommand
    return AdapterCommand.objects.filter(makerspace=space, command="snapshot", created_at__gte=month_start()).count()


def adapter_artifacts(space):
    from apps.devices.models import AdapterArtifact
    return AdapterArtifact.objects.filter(makerspace=space).exclude(status="purged").count()


def devices(space):
    from apps.devices.models import Device
    return Device.objects.filter(makerspace=space).exclude(status=Device.Status.REVOKED).count()


def machine_jobs_monthly(space):
    from apps.machines.models import MachineServiceRequest
    return MachineServiceRequest.objects.filter(makerspace=space, created_at__gte=month_start()).count()


def machine_sessions_monthly(space):
    from apps.machines.models_sessions import MachineSession
    return MachineSession.objects.filter(makerspace=space, created_at__gte=month_start()).count()


def storage_evidence_bytes(space):
    """Bytes of finalized, charged evidence photos whose object has not expired under retention."""
    from apps.evidence.models import EvidenceUploadFinalization
    rows = EvidenceUploadFinalization.objects.filter(evidence__makerspace=space, quota_charged=True).exclude(
        evidence__object_retention_state__status="expired")
    return int(rows.aggregate(total=Sum("size_bytes"))["total"] or 0)


def storage_public_images_bytes(space):
    """Managed bytes that are not evidence (public images first among them): total minus evidence."""
    from apps.makerspaces.limits_usage import _storage
    return max(0, _storage(space) - storage_evidence_bytes(space))


def member_cards_issued_monthly(space):
    """Member cards created this month, revoked ones included (churning cannot reset the quota)."""
    from apps.makerspaces.models import MemberCard
    return MemberCard.objects.filter(makerspace=space, created_at__gte=month_start()).count()


def staff_cards_issued_monthly(space):
    """Staff cards created this month, revoked ones included (churning cannot reset the quota)."""
    from apps.card_designs.models_staff_cards import StaffCard
    return StaffCard.objects.filter(makerspace=space, created_at__gte=month_start()).count()


def wallet_passes(space):
    from apps.card_designs.models import WalletPass
    return WalletPass.objects.filter(makerspace=space, voided_at__isnull=True).count()


def series_invites(space):
    from apps.events.models_invites import EventInvite
    return EventInvite.objects.filter(makerspace=space, series__isnull=False, revoked_at__isnull=True).count()


def checkin_lists(space):
    """The busiest event's live (not archived) lists: the limit applies to one event at a time."""
    from django.db.models import Count
    from apps.events.models_checkin_lists import EventCheckInList
    rows = EventCheckInList.objects.filter(makerspace=space, archived_at__isnull=True).values("event").annotate(
        n=Count("pk")).order_by("-n")[:1]
    return rows[0]["n"] if rows else 0


def event_badge_prints_monthly(space):
    """Badge print receipts reported this month (offline prints count when they sync)."""
    from apps.events.models_badge_prints import EventBadgePrint
    return EventBadgePrint.objects.filter(makerspace=space, reported_at__gte=month_start()).count()


def photo_cutout_jobs_monthly(space):
    """Background-removal jobs queued this month (a re-run of one holder's photo counts again).

    Counted from the append-only audit trail, never from live CardPhotoCutout rows: a re-run deletes the old row and a
    discard deletes its row, so a row count would let re-runs slip past the quota (decision 344(a))."""
    from apps.audit.models import AuditLog
    return AuditLog.objects.filter(action="card.photo_cutout_requested", makerspace=space,
                                   created_at__gte=month_start()).count()


def card_templates(space):
    """Card and certificate templates a space has saved or imported."""
    from apps.card_designs.models import CardTemplate
    return CardTemplate.objects.filter(makerspace=space).count()


def hackathon_stages(space):
    """The busiest event's submission stages: the limit applies to one event at a time."""
    from django.db.models import Count
    from apps.events.submissions.models_stages import SubmissionStage
    rows = SubmissionStage.objects.filter(event__makerspace=space).values("event").annotate(
        n=Count("pk")).order_by("-n")[:1]
    return rows[0]["n"] if rows else 0


def saved_views(space):
    """The most views one person holds on one event's list: the limit applies per person and list."""
    from django.db.models import Count
    from apps.operations.models_saved_views import SavedView
    rows = SavedView.objects.filter(makerspace=space, state__has_key="event").values(
        "owner", "entity", "state__event").annotate(n=Count("pk")).order_by("-n")[:1]
    return rows[0]["n"] if rows else 0


COUNTERS = {fn.__name__: fn for fn in (
    member_cards_issued_monthly, staff_cards_issued_monthly, wallet_passes,
    event_registrations_monthly, shop_orders_monthly, shop_products, membership_plans, donation_campaigns,
    bookable_spaces, boxes, organizations_linked, analytics_connections, report_exports_monthly, kiosk_stations,
    devices, machine_jobs_monthly, machine_sessions_monthly, storage_evidence_bytes, storage_public_images_bytes, webhook_endpoints,
    member_units, collection_sheet_rows_monthly, series_invites, checkin_lists, saved_views, hackathon_stages,
    event_badge_prints_monthly, paired_displays, adapter_bridges, adapter_watch_streams, adapter_snapshots, adapter_artifacts, photo_cutout_jobs_monthly, card_templates)}

from .extra_quota_counters_0120 import COUNTERS_0120  # noqa: E402  (0.12.0 keys; imports month_start from here)

COUNTERS.update(COUNTERS_0120)
