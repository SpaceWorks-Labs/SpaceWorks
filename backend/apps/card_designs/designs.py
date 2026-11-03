"""Save, submit, approve, reject and publish card designs (SPEC §5.1 design approval).

Autosave writes a draft revision (compare-and-swap on `revision`); holders keep
rendering `published_document` until a publish. Publishing needs no approval for an
approver, or when no level asks for it; otherwise the editor submits the revision
and an approver publishes it by approving. Editing a submitted design withdraws it.
Every step is audited; autosaves at most once per design per 10 minutes.
"""
from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.audit import services as audit

from . import approval
from .layout import asset_ids, normalize_document
from .models import CardDesign, CardDesignApproval, CardDesignAsset, CardDesignRevision

SAVE_AUDIT_WINDOW = timedelta(minutes=10)


class DesignConflict(ValidationError):
    status_code = 409
    default_code = "card_design_conflict"


def asset_colours(makerspace_id, document):
    ids = asset_ids(document)
    rows = CardDesignAsset.objects.filter(makerspace_id=makerspace_id, asset_id__in=ids, ready=True)
    found = {str(row.asset_id): row.mean_colour or "#808080" for row in rows}
    missing = ids - set(found)
    if missing:
        raise ValidationError({"document": "An image in this design was not uploaded to this space."})
    return found


def validated(makerspace_id, document, *, check_contrast=True):
    """A draft saves with unreadable text (the designer warns as you go); publish and submit refuse it."""
    from .layout import upgrade
    upgraded = upgrade(document)
    colours = asset_colours(makerspace_id, upgraded) if isinstance(upgraded, dict) else {}
    return normalize_document(upgraded, asset_colours=colours, check_contrast=check_contrast)



@transaction.atomic
def save(actor, design, document, *, expected_revision, acted_for=None):
    design = CardDesign.objects.select_for_update().get(pk=design.pk)
    if expected_revision != design.revision:
        raise DesignConflict({"revision": "Someone else saved this design. Reload to see their changes."})
    clean = validated(design.makerspace_id, document, check_contrast=False)
    if clean == design.document:
        return design
    design.document = clean
    design.revision += 1
    design.updated_by = actor
    pending = design.approvals.filter(decision=CardDesignApproval.Decision.PENDING).first()
    if pending:
        pending.decision, pending.decided_at = CardDesignApproval.Decision.WITHDRAWN, timezone.now()
        pending.save(update_fields=["decision", "decided_at"])
    if design.status != CardDesign.Status.PUBLISHED or pending:
        design.status = CardDesign.Status.DRAFT
    design.save()
    CardDesignRevision.objects.create(design=design, revision=design.revision, document=clean, created_by=actor)
    recent = CardDesignRevision.objects.filter(design=design, created_by=actor, revision__lt=design.revision,
                                               created_at__gte=timezone.now() - SAVE_AUDIT_WINDOW).exists()
    if not recent:
        audit.record(actor, "card_design.saved", makerspace=design.makerspace, target=design,
                     meta={"design_id": design.pk, "domain": design.domain, "revision": design.revision, "event_id": design.event_id, "programme_id": design.programme_id, "acted_for_organization_id": acted_for})
    return design


def _publish(actor, design, revision_document, *, acted_for=None):
    design.published_document = revision_document
    design.published_revision = design.revision
    design.published_at = timezone.now()
    design.status = CardDesign.Status.PUBLISHED
    design.save(update_fields=["published_document", "published_revision", "published_at", "status", "updated_at"])
    audit.record(actor, "card_design.published", makerspace=design.makerspace, target=design,
                 meta={"design_id": design.pk, "domain": design.domain, "revision": design.revision, "event_id": design.event_id, "programme_id": design.programme_id, "acted_for_organization_id": acted_for})
    from .notifications import design_published
    transaction.on_commit(lambda: design_published(design.pk), robust=True)


@transaction.atomic
def publish(actor, design, *, acted_for=None):
    design = CardDesign.objects.select_for_update().get(pk=design.pk)
    if approval.needs_approval(actor, design):
        raise PermissionDenied("This design needs approval. Submit it for approval instead.")
    _publish(actor, design, validated(design.makerspace_id, design.document), acted_for=acted_for)
    return design


@transaction.atomic
def submit(actor, design):
    design = CardDesign.objects.select_for_update().get(pk=design.pk)
    if not approval.needs_approval(actor, design):
        raise ValidationError({"detail": "You can publish this design directly."})
    if design.approvals.filter(decision=CardDesignApproval.Decision.PENDING).exists():
        raise ValidationError({"detail": "This design is already waiting for approval."})
    validated(design.makerspace_id, design.document)
    row = CardDesignApproval.objects.create(design=design, revision=design.revision, requested_by=actor)
    design.status = CardDesign.Status.PENDING_APPROVAL
    design.save(update_fields=["status", "updated_at"])
    audit.record(actor, "card_design.submitted", makerspace=design.makerspace, target=design,
                 meta={"design_id": design.pk, "domain": design.domain, "revision": design.revision, "event_id": design.event_id, "programme_id": design.programme_id, "approval_id": row.pk})
    from .notifications import design_awaiting_approval
    transaction.on_commit(lambda: design_awaiting_approval(row.pk), robust=True)
    return row


@transaction.atomic
def decide(actor, design, *, approve, note=""):
    design = CardDesign.objects.select_for_update().get(pk=design.pk)
    if not approval.can_approve(actor, design):
        raise PermissionDenied("Only an approver in this space can decide.")
    row = design.approvals.select_for_update().filter(decision=CardDesignApproval.Decision.PENDING).first()
    if row is None:
        raise ValidationError({"detail": "Nothing is waiting for approval."})
    if row.revision != design.revision:
        raise DesignConflict({"revision": "The design changed after it was submitted."})
    row.decision = CardDesignApproval.Decision.APPROVED if approve else CardDesignApproval.Decision.REJECTED
    row.decided_by, row.decided_at, row.note = actor, timezone.now(), (note or "")[:300]
    row.save(update_fields=["decision", "decided_by", "decided_at", "note"])
    if approve:
        audit.record(actor, "card_design.approved", makerspace=design.makerspace, target=design,
                     meta={"design_id": design.pk, "domain": design.domain, "revision": design.revision, "event_id": design.event_id, "programme_id": design.programme_id, "approval_id": row.pk})
    else:
        audit.record(actor, "card_design.rejected", makerspace=design.makerspace, target=design,
                     meta={"design_id": design.pk, "domain": design.domain, "revision": design.revision, "event_id": design.event_id, "programme_id": design.programme_id, "approval_id": row.pk})
    if approve:
        _publish(actor, design, validated(design.makerspace_id, design.document))
    else:
        design.status = CardDesign.Status.DRAFT if design.published_document is None else CardDesign.Status.PUBLISHED
        design.save(update_fields=["status", "updated_at"])
    return row


@transaction.atomic
def reset(actor, design, template_document):
    """Start again from a template; the published design is untouched until a publish."""
    design = CardDesign.objects.select_for_update().get(pk=design.pk)
    result = save(actor, design, template_document, expected_revision=design.revision)
    audit.record(actor, "card_design.reset", makerspace=design.makerspace, target=design,
                 meta={"design_id": result.pk, "domain": result.domain, "revision": result.revision})
    return result
