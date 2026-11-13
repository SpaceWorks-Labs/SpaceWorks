"""Background clean-up as a job (#133, Q-I3): candidate first, the person decides.

The holder (or staff) asks for a clean-up of the card's current photo; the job writes
a candidate object; accepting replaces the photo and deletes the original, discarding
deletes the candidate. Nothing changes on the card until the person accepts.
"""
from django.utils.translation import gettext
from django.db import transaction
from rest_framework.exceptions import ValidationError

from apps.audit import services as audit

from .holders import spec_for
from .models import CardJob
from .storage import delete_quietly, get_bytes, put_bytes


def request(actor, kind, card):
    from . import segmentation
    from .jobs import enqueue
    if not segmentation.available():
        raise ValidationError({"detail": gettext("Photo clean-up is not set up on this server.")})
    if not spec_for(kind).photo_bytes(card):
        raise ValidationError({"detail": gettext("Add a photo first.")})
    scope = {"member_card": "member_cards", "programme_card": "id_programme", "event_card": "event",
             "staff_card": "staff_cards"}[kind]
    job, _created = enqueue(actor, card.makerspace, CardJob.Kind.PHOTO_CLEANUP, scope=scope, targets=[card.pk],
                            params={}, revision=f"{kind}:{card.pk}:{getattr(card, 'photo_object_key', '')}")
    return job


def run_cleanup(job):
    from apps.tenant_migration.gate_runtime import assert_write_allowed
    assert_write_allowed(job.makerspace_id)
    from . import segmentation
    from .jobs import holder_kind
    kind = holder_kind(job)
    spec = spec_for(kind)
    card = spec.model().objects.filter(pk=job.targets[0]).first()
    data = spec.photo_bytes(card) if card else None
    if not data:
        return False
    key = f"card-jobs/{job.makerspace_id}/{job.pk}/candidate.png"
    put_bytes(key, segmentation.remove_background(data), "image/png")
    job.parts = [key]
    return True


def _candidate(job):
    if job.kind != CardJob.Kind.PHOTO_CLEANUP or job.state != CardJob.State.SUCCEEDED or not job.result_key:
        raise ValidationError({"detail": gettext("No cleaned photo is waiting.")})
    return job.result_key


@transaction.atomic
def accept(actor, kind, card, job):
    key = _candidate(job)
    data = get_bytes(key)
    if kind == "member_card":
        from apps.makerspaces.member_card_storage import replace_photo_bytes
        replace_photo_bytes(actor, card, data)
    else:
        from .photos import attach_bytes
        attach_bytes(actor, kind, card, data, consent=True)
    audit.record(actor, "card.photo_cleanup_accepted", makerspace=card.makerspace, target=card,
                 meta={"card_id": card.pk, "job_id": job.pk})
    CardJob.objects.filter(pk=job.pk).update(result_key="", result_size=0)
    transaction.on_commit(lambda: delete_quietly(key))


def discard(actor, job):
    key = _candidate(job)
    CardJob.objects.filter(pk=job.pk).update(result_key="", result_size=0)
    delete_quietly(key)
