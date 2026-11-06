"""One initial gallery publication; amendments are explicit immutable history."""

from django.utils.translation import gettext
from django.http import Http404
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.events.judging.boundary import audit, changed, command, envelope, mutation, notice, owned
from apps.events.judging.errors import ProgrammeError, require_version
from apps.events.judging.models_results import EventResultRevision
from apps.events.judging.models_scoring import JudgingReason
from apps.events.judging.ports import runtime
from apps.events.judging.serializers import validated
from .gallery_models import (
    GalleryAmendment, GalleryConsent, GalleryEntry, GalleryEntryAsset, GalleryEntryLink, GalleryPublication,
)
from .gallery_serializers import GalleryAmendInput, GalleryHideInput, GalleryPublishInput, GalleryResultCorrectionInput


def _result(event_id, result_id):
    if result_id is None:
        return None
    result = EventResultRevision.objects.filter(event_id=event_id, pk=result_id).first()
    if not result:
        raise Http404
    return result


def _entry(publication, snapshot_id, *, selection_revision=1):
    snapshot = runtime().snapshot(snapshot_id)
    consent = GalleryConsent.objects.filter(event_id=publication.event_id, team_id=snapshot.team_id,
                                            snapshot_id=snapshot_id, metadata_public=True).first()
    if not consent or snapshot.event_id != publication.event_id or not snapshot.current or not snapshot.eligible:
        raise ValidationError({"snapshot_ids": gettext("Select only eligible, explicitly public frozen submissions.")})
    from .stage_gallery import gallery_stage_allowed
    if not gallery_stage_allowed(publication.event_id, snapshot):
        # #178/#179: the gallery shows the last stage (or an S18 public stage's passing teams), so a team
        # eliminated earlier never appears.
        raise ValidationError({"snapshot_ids": gettext("The gallery shows each project's final-stage submission.")})
    items = list(consent.items.filter(active=True))
    if (not {i.asset_id for i in items if i.asset_id} <= set(snapshot.public_asset_ids)
            or not {i.link_id for i in items if i.link_id} <= {link.id for link in snapshot.public_links}):
        raise ValidationError({"snapshot_ids": gettext("Public item consent changed. Review the selection.")})
    entry = GalleryEntry.objects.create(event_id=publication.event_id, publication=publication, snapshot_id=snapshot.id,
        title=snapshot.title, description=snapshot.description, metadata_generation=consent.metadata_generation,
        selection_revision=selection_revision)
    links = {link.id: link for link in snapshot.public_links}
    for item in items:
        if item.asset_id:
            GalleryEntryAsset.objects.create(entry=entry, asset_id=item.asset_id, consent_generation=item.generation)
        else:
            link = links[item.link_id]
            GalleryEntryLink.objects.create(entry=entry, link_id=link.id, url=link.url, kind=link.kind,
                                            consent_generation=item.generation)
    return entry


def publish(event_id, *, actor, data):
    values = validated(GalleryPublishInput, data)
    with mutation(event_id, actor, permission=None, gallery=True) as (event, _):
        def run():
            if GalleryPublication.objects.filter(event=event).exists():
                raise ProgrammeError("gallery_already_published", "The initial gallery was already published. Use an explicit amendment.")
            if values["expected_version"] != 0:
                raise ProgrammeError("stale_version", "This item changed.", current_version=0)
            publication = GalleryPublication.objects.create(event=event, published_at=timezone.now(), published_by=actor,
                result_revision=_result(event_id, values["result_revision_id"]))
            for snapshot_id in values["snapshot_ids"]:
                _entry(publication, snapshot_id)
            audit(event, actor, "gallery_published", publication, count=len(values["snapshot_ids"]), version=publication.version)
            notice(event, "gallery_published", publication.pk, publication.version)
            return envelope(publication, state="published", count=len(values["snapshot_ids"]))
        return command(event, actor, values, path="gallery/publish", run=run)


def hide(event_id, entry_id, *, actor, data):
    values = validated(GalleryHideInput, data)
    with mutation(event_id, actor, permission=None, gallery=True) as (event, _):
        def run():
            entry = owned(GalleryEntry, event_id, entry_id, expected=values["expected_version"])
            if not values["hidden"]:
                from .gallery_projection import live_entry
                live_entry(entry, include_hidden=True)
            entry.hidden_at = timezone.now() if values["hidden"] else None
            entry.hidden_reason = JudgingReason.objects.create(event=event, makerspace_id=event.makerspace_id,
                                                                actor=actor, body=values["reason"])
            return changed(event, actor, "gallery_entry_hidden" if values["hidden"] else "gallery_entry_unhidden", entry,
                           hidden=values["hidden"])
        return command(event, actor, values, path=f"gallery/entries/{entry_id}/hide", run=run)


def amend(event_id, *, actor, data):
    """Explicit manager route; never silently expand the initial one-shot selection."""
    values = validated(GalleryAmendInput, data)
    with mutation(event_id, actor, permission=None, gallery=True) as (event, _):
        def run():
            publication = GalleryPublication.objects.select_for_update().filter(event=event).first()
            if not publication:
                raise Http404
            require_version(publication, values["expected_version"])
            old = publication.entries.filter(snapshot_id=values["snapshot_id"]).order_by("-selection_revision").first()
            entry = _entry(publication, values["snapshot_id"], selection_revision=old.selection_revision + 1 if old else 1)
            # New snapshots supersede public entries from the same team, preserving their history.
            snapshot = runtime().snapshot(values["snapshot_id"])
            for prior in publication.entries.exclude(pk=entry.pk).order_by("pk"):
                if runtime().snapshot(prior.snapshot_id).team_id == snapshot.team_id:
                    prior.hidden_at = timezone.now()
                    prior.version += 1
                    prior.save()
            reason = JudgingReason.objects.create(event=event, makerspace_id=event.makerspace_id, actor=actor, body=values["reason"])
            publication.version += 1
            publication.active = True
            publication.save()
            GalleryAmendment.objects.create(publication=publication, entry=entry, revision=publication.version,
                                             reason=reason, actor=actor)
            audit(event, actor, "gallery_amended", publication, version=publication.version, entry_id=entry.pk)
            return envelope(publication, entry_id=entry.pk, state="published")
        return command(event, actor, values, path="gallery/amend", run=run)


def correct_result(event_id, *, actor, data):
    values = validated(GalleryResultCorrectionInput, data)
    with mutation(event_id, actor, permission=None, gallery=True) as (event, _):
        def run():
            publication = GalleryPublication.objects.select_for_update().filter(event=event).first()
            if publication is None:
                raise Http404
            require_version(publication, values["expected_version"])
            result = _result(event_id, values["result_revision_id"])
            publication.result_revision = result
            publication.version += 1
            publication.save()
            reason = JudgingReason.objects.create(event=event, makerspace_id=event.makerspace_id, actor=actor, body=values["reason"])
            GalleryAmendment.objects.create(publication=publication, revision=publication.version, result_revision=result,
                                            reason=reason, actor=actor)
            audit(event, actor, "gallery_result_corrected", publication, version=publication.version, result_id=result.pk)
            return envelope(publication, state="published")
        return command(event, actor, values, path="gallery/correct-result", run=run)
