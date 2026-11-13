"""Clone only current person-free designs with independently owned artwork."""
from .studio_assets import image_ids, remap
from django.utils.translation import gettext
from copy import deepcopy
from uuid import uuid4
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from apps.audit.services import record
from apps.events.models_certificate_templates import EventCertificateArtwork, EventCertificateTemplateRevision
from apps.makerspaces import limits
from .print_models import EventBadgeTemplateRevision
from . import print_storage
from apps.transaction_guards import in_domain_transaction


class CleanupStorage:
    @staticmethod
    def delete_object(key):
        print_storage.delete(key)
        return True


def identities(event):
    certificate = EventCertificateTemplateRevision.objects.filter(event=event, certificate_kind="").select_related("artwork").first()
    badge = EventBadgeTemplateRevision.objects.filter(event=event).order_by("-pk").first()
    return certificate, badge


def prepare_designs(event, copies):
    if in_domain_transaction():
        raise RuntimeError("Prepare clone artwork before domain locks.")
    certificate, badge = identities(event)
    selected = set()
    documents = [row.parameters if hasattr(row, "parameters") else row.document for row in (certificate, badge) if row]
    for document in documents:
        selected.update(image_ids(document))
    rows = EventCertificateArtwork.objects.filter(event=event, promoted_at__isnull=False)
    resources = list(rows.filter(resource_id__in=selected))
    if certificate and certificate.artwork_id and all(r.pk != certificate.artwork_id for r in resources):
        resources.append(certificate.artwork)
    if not selected <= {str(row.resource_id) for row in resources}:
        raise ValidationError(gettext("Install every source design image before cloning."))
    from apps.events.certificate_artwork_storage import read_artwork
    prepared = []
    for row in resources:
        content = read_artwork(row.object_key, row.version_id, row.sha256)
        if len(content) != row.size_bytes:
            raise ValidationError(gettext("The source artwork size changed."))
        if copies.total_bytes + len(content) > copies.max_total_bytes:
            raise ValidationError(gettext("The clone asset limit was exceeded."))
        copies.total_bytes += len(content)
        resource_id = uuid4()
        key = f"events/certificate-artwork/{event.makerspace_id}/{resource_id}.png"
        copies.created.append((CleanupStorage, key))
        print_storage.put(key, content, "image/png")
        prepared.append({"source_id": row.pk, "source_resource": str(row.resource_id),
            "source_key": row.object_key, "resource_id": resource_id, "object_key": key,
            "sha256": row.sha256, "size_bytes": len(content)})
    return {"certificate_id": certificate.pk if certificate else None, "badge_id": badge.pk if badge else None,
        "certificate": deepcopy(certificate.parameters) if certificate else None,
        "badge": deepcopy(badge.document) if badge else None, "stock": badge.stock if badge else None,
        "artwork_id": certificate.artwork_id if certificate else None, "resources": prepared}


def copy_designs_locked(*, source, target, actor, prepared):
    certificate, badge = identities(source)
    if (certificate.pk if certificate else None, badge.pk if badge else None) != (prepared["certificate_id"], prepared["badge_id"]):
        raise ValidationError(gettext("Source designs changed. Retry the copy."))
    mapping, by_id = {}, {}
    for value in prepared["resources"]:
        if not EventCertificateArtwork.objects.filter(event=source, pk=value["source_id"],
                object_key=value["source_key"], sha256=value["sha256"], size_bytes=value["size_bytes"],
                promoted_at__isnull=False).exists():
            raise ValidationError(gettext("Source artwork changed. Retry the copy."))
        limits.add_storage(target.makerspace, value["size_bytes"])
        row = EventCertificateArtwork.objects.create(event=target, resource_id=value["resource_id"],
            object_key=value["object_key"], sha256=value["sha256"], size_bytes=value["size_bytes"], promoted_at=timezone.now())
        mapping[value["source_resource"]] = str(row.resource_id)
        by_id[value["source_id"]] = row
    for key, model in (("certificate", EventCertificateTemplateRevision), ("badge", EventBadgeTemplateRevision)):
        document = deepcopy(prepared[key])
        if document is None:
            continue
        remap(document, mapping)
        values = {"parameters": document, "artwork": by_id.get(prepared["artwork_id"])} if key == "certificate" else {"document": document, "stock": prepared["stock"]}
        row = model.objects.create(event=target, **values)
        record(actor, "event.certificate_template_saved" if key == "certificate" else "event.badge_design_saved",
            makerspace=target.makerspace, target=row, meta={"source_event_id": source.pk})
