"""Release-0.12 card-studio and event-certificate reports: counts only, no holder is named."""

from django.db.models import Count

from apps.operations.reports_r2_common import metric_report


def _count_by(queryset, field, prefix):
    rows = queryset.order_by().values(field).annotate(n=Count("pk")).order_by(field)
    return [(f"{prefix}:{row[field]}", row["n"]) for row in rows]


def _studio_rows(space, start, end):
    from apps.card_designs.models import CardDesign, CardJob, WalletPass
    jobs = CardJob.objects.filter(makerspace=space, created_at__gte=start, created_at__lt=end)
    passes = WalletPass.objects.filter(makerspace=space)
    return [
        *_count_by(CardDesign.objects.filter(makerspace=space), "status", "designs"),
        ("jobs_requested", jobs.count()),
        *_count_by(jobs, "state", "jobs"),
        *_count_by(jobs, "kind", "jobs_kind"),
        ("wallet_passes_live", passes.filter(voided_at__isnull=True).count()),
        ("wallet_passes_issued_in_period", passes.filter(created_at__gte=start, created_at__lt=end).count()),
        ("wallet_passes_voided", passes.filter(voided_at__isnull=False).count()),
    ]


def build_card_studio_activity(makerspace_id, *, limit=None, date_range=None, actor=None, grain=None):
    return metric_report(makerspace_id, ("membership",), _studio_rows, limit=limit, date_range=date_range,
                         definition="Card designs by state, print/email/wallet jobs and wallet passes, in counts.")


def _certificate_rows(space, start, end):
    from apps.events.models import EventAttendanceCertificate
    from apps.events.certificates.models import CertificateIssueBatch
    issued = EventAttendanceCertificate.objects.filter(
        event__makerspace=space, issued_at__gte=start, issued_at__lt=end)
    batches = CertificateIssueBatch.objects.filter(
        event__makerspace=space, created_at__gte=start, created_at__lt=end)
    return [
        ("certificates_issued", issued.count()),
        ("certificates_revoked", issued.filter(revoked_at__isnull=False).count()),
        ("public_verification_on", issued.filter(public_verification_enabled=True).count()),
        *_count_by(issued, "kind", "kind"),
        *_count_by(issued, "status", "status"),
        ("batches_started", batches.count()),
        *_count_by(batches, "state", "batch"),
    ]


def build_event_certificates_issued(makerspace_id, *, limit=None, date_range=None, actor=None, grain=None):
    return metric_report(makerspace_id, ("events",), _certificate_rows, limit=limit, date_range=date_range,
                         definition="Event certificates issued, revoked and batched, in counts; no recipient appears.")
