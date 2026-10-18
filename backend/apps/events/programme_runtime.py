"""Query-free runtime registrations; retained data catalogues live outside this module."""
from apps.integrations.notification_sources import NotificationSource, register_source


def application_notice_eligible(envelope):
    from .hackathons.admission_models import HackathonApplication
    from .hackathons.admission_notifications import MESSAGES
    from apps.makerspaces.platform import feature_enabled, module_enabled
    from apps.makerspaces.servability import is_servable

    if envelope.event not in MESSAGES:
        return False
    row = HackathonApplication.objects.filter(pk=envelope.source_id,
        event_id=envelope.context.get("event_id"), member_id=envelope.recipient_id,
    ).select_related("event__makerspace").first()
    from .hackathons.admission_models import HackathonConfig
    return bool(row and str(row.version) == str(envelope.revision)
        and row.event.makerspace_id == envelope.makerspace_id
        and is_servable(row.event.makerspace) and module_enabled(row.event.makerspace, "events")
        and feature_enabled(row.event.makerspace, "events.hackathons")
        and HackathonConfig.objects.filter(event_id=row.event_id, enabled=True).exists())


def template_catalogue(*, kind, theme, stock=None):
    from .default_templates import CERTIFICATE_SEEDS, badge_seed
    from .default_templates.manifest import BADGE_FAMILIES, THEMES, STOCKS
    if theme not in THEMES:
        raise ValueError("Unknown template theme.")
    if kind == "certificate":
        return tuple(seed for seed in CERTIFICATE_SEEDS if seed["theme"] == theme)
    if kind == "badge" and stock in STOCKS:
        return tuple(badge_seed(family, theme, stock) for family in BADGE_FAMILIES)
    raise ValueError("Unknown template kind or stock.")


def certificate_document(certificate_id, *, makerspace_id, recipient_id, revision):
    from .models_certificates import EventAttendanceCertificate
    from .certificates.notifications import document_for_recipient
    from apps.integrations.notification_certificate_media import CertificateDocument

    row = EventAttendanceCertificate.objects.filter(pk=certificate_id, recipient_member_id=recipient_id,
        revision=revision, status="active").select_related("registration", "event").first()
    if row is None:
        return None
    origin = ((row.registration.registered_via_makerspace_id if row.registration_id else None)
              or row.event.makerspace_id)
    if origin != makerspace_id:
        return None
    from .certificates.owner_queries import owner_certificate
    owner_certificate(row.recipient_member, origin, row.pk)
    result = document_for_recipient(certificate_id=certificate_id, recipient_id=recipient_id, revision=revision)
    if (result is None or type(result.get("size_bytes")) is not int
            or result["size_bytes"] <= 0 or len(result.get("sha256", "")) != 64):
        return None
    return CertificateDocument(certificate_id=row.pk, event_id=row.event_id,
        makerspace_id=origin, storage_makerspace_id=row.event.makerspace_id,
        owner_member_id=recipient_id, revision=str(row.revision), object_key=result["object_key"],
        sha256=result["sha256"], size_bytes=result["size_bytes"], filename=result["filename"])


def register_programme_runtime():
    from .certificates.seeds import install_catalogue
    from apps.integrations.notification_certificate_media import register_certificate_resolver
    register_source("events.application", NotificationSource(application_notice_eligible))
    install_catalogue(template_catalogue)
    register_certificate_resolver(certificate_document)
