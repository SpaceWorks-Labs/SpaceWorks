"""Owner-only immutable certificate PDFs; no badges, submissions or room sends.

The legacy resolver supports attendance certificates. E installs its resolver for
the extended contribution/award subjects; generic transports keep the same seam.
"""
import hashlib
import re
from dataclasses import dataclass
from typing import Callable
from .notification_attachment_sources import AttachmentReference, DocumentDeliveryError

MAX_BYTES = 5 * 1024 * 1024


@dataclass(frozen=True)
class CertificateDocument:
    certificate_id: int
    event_id: int
    makerspace_id: int
    storage_makerspace_id: int
    owner_member_id: int
    revision: str
    object_key: str
    sha256: str
    size_bytes: int
    filename: str


_resolver: Callable | None = None


def register_certificate_resolver(resolver):
    """E supplies live subject/feature/profile/standing checks, no query at startup."""
    global _resolver
    if _resolver is not None and _resolver is not resolver:
        raise ValueError("Duplicate certificate media resolver.")
    _resolver = resolver


def _legacy_resolver(certificate_id, *, makerspace_id, recipient_id, revision):
    from apps.accounts import rbac
    from apps.events.models import EventAttendanceCertificate
    from apps.makerspaces.platform import module_enabled
    from apps.makerspaces.servability import is_servable
    from apps.notifications.inbox import eligible_owner
    rows = EventAttendanceCertificate.objects.select_related(
        "registration__event__makerspace", "registration__member", "registration__registered_via_makerspace")
    # A collaborative attendee's notification belongs to the durable provenance
    # space. The private PDF still belongs to the host; no unrelated venue joins.
    scoped = rbac.scope_notification_policy(rows, makerspace_id=makerspace_id,
        field="registration__event__makerspace_id") | rbac.scope_notification_policy(
        rows, makerspace_id=makerspace_id, field="registration__registered_via_makerspace_id")
    certificate = scoped.filter(
            pk=certificate_id, revision=revision, status="active", registration__member_id=recipient_id,
            registration__status="attended").first()
    if certificate is None:
        raise DocumentDeliveryError("document_not_authorized")
    event = certificate.registration.event
    origin = event.makerspace if event.makerspace_id == makerspace_id else certificate.registration.registered_via_makerspace
    if (not is_servable(event.makerspace) or not module_enabled(event.makerspace, "events")
            or origin is None or not is_servable(origin) or not module_enabled(origin, "events")
            or not eligible_owner(origin, recipient_id) or not eligible_owner(event.makerspace, recipient_id)):
        raise DocumentDeliveryError("document_not_authorized")
    return CertificateDocument(certificate.pk, event.pk, makerspace_id, event.makerspace_id, recipient_id, str(certificate.revision),
        certificate.object_key, certificate.sha256, certificate.size_bytes,
        f"certificate-{certificate.serial}.pdf")


def authorize(reference, *, makerspace_id, recipient_id):
    from apps.separability.tombstones import app_is_tombstoned
    if (reference.source_kind != "events.certificate" or reference.kind != "certificate"
            or not re.fullmatch(r"[1-9][0-9]{0,9}", reference.revision)
            or int(reference.revision) > 2147483647 or app_is_tombstoned("events")):
        raise DocumentDeliveryError("document_not_authorized")
    result = (_resolver or _legacy_resolver)(reference.document_id, makerspace_id=makerspace_id,
        recipient_id=recipient_id, revision=reference.revision)
    if (not isinstance(result, CertificateDocument) or result.certificate_id != reference.document_id
            or result.makerspace_id != makerspace_id or result.owner_member_id != recipient_id
            or type(result.storage_makerspace_id) is not int or result.storage_makerspace_id < 1
            or result.revision != reference.revision or not re.fullmatch(r"[a-f0-9]{64}", result.sha256)
            or type(result.size_bytes) is not int or result.size_bytes < 5):
        raise DocumentDeliveryError("document_not_authorized")
    if result.size_bytes > MAX_BYTES:
        raise DocumentDeliveryError("document_size_exceeded")
    from apps.tenant_migration.gate_runtime import assert_write_allowed
    for tenant_id in sorted({result.makerspace_id, result.storage_makerspace_id}):
        assert_write_allowed(tenant_id)
    return result


def references(envelope):
    # A revocation notice intentionally remains a navigation-only message.
    if envelope.event == "certificate_revoked":
        return ()
    if envelope.event != "certificate_ready":
        raise DocumentDeliveryError("document_not_authorized")
    from .notification_sources import source_eligible
    if not source_eligible(envelope):
        raise DocumentDeliveryError("document_not_authorized")
    certificate_id = envelope.context.get("certificate_id")
    if type(certificate_id) is not int or str(certificate_id) != str(envelope.source_id):
        raise DocumentDeliveryError("document_not_authorized")
    reference = AttachmentReference("events.certificate", certificate_id, "certificate", str(envelope.revision))
    document = authorize(reference, makerspace_id=envelope.makerspace_id, recipient_id=envelope.recipient_id)
    if document.event_id != envelope.context.get("event_id"):
        raise DocumentDeliveryError("document_not_authorized")
    return (reference,)


def render(reference, *, makerspace_id, recipient_id):
    import boto3
    from botocore.config import Config
    from django.conf import settings
    document = authorize(reference, makerspace_id=makerspace_id, recipient_id=recipient_id)
    body = None
    try:
        client = boto3.client("s3", endpoint_url=settings.AWS_S3_ENDPOINT_URL,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID, aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_S3_REGION_NAME, config=Config(connect_timeout=2, read_timeout=2,
                retries={"max_attempts": 0}, signature_version=settings.AWS_S3_SIGNATURE_VERSION,
                s3={"addressing_style": settings.AWS_S3_ADDRESSING_STYLE}))
        response = client.get_object(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=document.object_key)
        body = response["Body"]
        if response.get("ContentLength") != document.size_bytes:
            raise DocumentDeliveryError("document_render_failed")
        pdf = body.read(document.size_bytes + 1)
        if len(pdf) != document.size_bytes or hashlib.sha256(pdf).hexdigest() != document.sha256:
            raise DocumentDeliveryError("document_render_failed")
    except DocumentDeliveryError:
        raise
    except Exception:
        raise DocumentDeliveryError("document_render_failed") from None
    finally:
        if body is not None:
            try:
                body.close()
            except Exception:
                # A cleanup failure must not leak storage exception text or reopen
                # a consumed grant. Policy/render errors above remain authoritative.
                pass
    return document.filename, pdf, "application/pdf"
