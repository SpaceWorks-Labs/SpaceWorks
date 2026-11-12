"""Any active sealed teammate can withdraw; only an eligible leader can regrant.

Generation counters prevent a later regrant from reviving a previously issued
gallery URL. Publishing an amendment is always a separate manager action.
"""

from django.utils.translation import gettext
from django.http import Http404

from apps.events.judging.boundary import active_member, audit, command, mutation, notice
from apps.events.judging.errors import ProgrammeError, require_version
from apps.events.judging.ports import runtime
from apps.events.judging.serializers import validated
from .gallery_models import GalleryConsent, GalleryConsentItem, GalleryConsentRevision, GalleryPublication
from .gallery_serializers import GalleryGrantInput, GalleryWithdrawInput


def team_snapshot(event_id, team_id, actor, *, snapshot_id=None, leader=False):
    active_member(actor)
    if snapshot_id:
        snapshot = runtime().snapshot(snapshot_id)
    else:
        stored = GalleryConsent.objects.filter(event_id=event_id, team_id=team_id).first()
        if stored:
            snapshot = runtime().snapshot(stored.snapshot_id)
        else:
            from .stage_judging import stage_snapshots  # #178: consent is given for the final-stage work.
            from .stage_runtime import last_stage_id
            snapshot = next((s for s in stage_snapshots(event_id, last_stage_id(event_id))
                             if s.team_id == team_id and s.current), None)
    if snapshot is None or snapshot.event_id != event_id or snapshot.team_id != team_id:
        raise Http404
    runtime().require_team_member(event_id=event_id, team_id=team_id, member_id=actor.pk,
                                  sealed_member_ids=snapshot.member_ids, leader=leader)
    if leader and (not snapshot.eligible or not snapshot.current):
        raise Http404
    return snapshot


def selection(row):
    items = list(row.items.filter(active=True)) if row else []
    return {"metadata_public": bool(row and row.metadata_public),
            "asset_ids": sorted(i.asset_id for i in items if i.asset_id),
            "link_ids": sorted(i.link_id for i in items if i.link_id)}


def project_owner(event_id, team_id, *, actor):
    team_snapshot(event_id, team_id, actor)
    row = GalleryConsent.objects.filter(event_id=event_id, team_id=team_id).first()
    return {"team_id": team_id, "version": row.version if row else 0, **selection(row),
            "publication_state": "published" if GalleryPublication.objects.filter(event_id=event_id).exists() else "unpublished"}


def _record(row, actor, action, scope):
    GalleryConsentRevision.objects.create(consent=row, revision=row.version, actor=actor, action=action,
                                          scope=scope, selection=selection(row))


def grant(event_id, team_id, *, actor, data):
    values = validated(GalleryGrantInput, data)
    team_snapshot(event_id, team_id, actor, snapshot_id=values["snapshot_id"], leader=True)
    with mutation(event_id, actor, owner=True) as (event, locks):
        def run():
            runtime().lock_team(event_id=event_id, team_id=team_id, locks=locks)
            snapshot = team_snapshot(event_id, team_id, actor, snapshot_id=values["snapshot_id"], leader=True)
            if (not set(values["asset_ids"]) <= set(snapshot.public_asset_ids)
                    or not set(values["link_ids"]) <= {link.id for link in snapshot.public_links}):
                raise Http404
            row = GalleryConsent.objects.select_for_update().filter(event=event, team_id=team_id).first()
            if row:
                require_version(row, values["expected_version"])
                new_generation = not row.metadata_public or row.snapshot_id != snapshot.id
                row.metadata_generation += int(new_generation)
                row.snapshot_id, row.metadata_public = snapshot.id, True
                row.version += 1
            else:
                if values["expected_version"] != 0:
                    raise ProgrammeError("stale_version", gettext("This item changed."), current_version=0)
                row = GalleryConsent(event=event, team_id=team_id, snapshot_id=snapshot.id, metadata_public=True)
                new_generation = True
            row.save()
            desired = {(pk, None) for pk in values["asset_ids"]} | {(None, pk) for pk in values["link_ids"]}
            existing = {(item.asset_id, item.link_id): item for item in row.items.all()}
            for key in set(existing) | desired:
                item = existing.get(key)
                if item:
                    if key in desired and (not item.active or new_generation):
                        item.generation += 1
                    item.active = key in desired
                    item.save()
                elif key in desired:
                    GalleryConsentItem.objects.create(consent=row, asset_id=key[0], link_id=key[1], active=True)
            _record(row, actor, "granted", "all")
            audit(event, actor, "gallery_consent_granted", row, version=row.version)
            published = GalleryPublication.objects.filter(event=event).exists()
            return {"team_id": team_id, "version": row.version, **selection(row),
                    "publication_state": "amendment_required" if published else "unpublished"}
        return command(event, actor, values, path=f"teams/{team_id}/gallery-consent/grant", run=run)


def withdraw(event_id, team_id, *, actor, data):
    values = validated(GalleryWithdrawInput, data)
    team_snapshot(event_id, team_id, actor)
    with mutation(event_id, actor, owner=True) as (event, locks):
        def run():
            runtime().lock_team(event_id=event_id, team_id=team_id, locks=locks)
            snapshot = team_snapshot(event_id, team_id, actor)
            row = GalleryConsent.objects.select_for_update().filter(event=event, team_id=team_id).first()
            if not row:
                raise Http404
            require_version(row, values["expected_version"])
            known_assets = set(row.items.filter(asset__isnull=False).values_list("asset_id", flat=True))
            known_links = set(row.items.filter(link__isnull=False).values_list("link_id", flat=True))
            if not set(values["asset_ids"]) <= known_assets or not set(values["link_ids"]) <= known_links:
                raise Http404
            if values["scope"] == "all":
                row.metadata_public = False
            for item in row.items.filter(active=True).order_by("pk"):
                if values["scope"] == "all" or item.asset_id in values["asset_ids"] or item.link_id in values["link_ids"]:
                    item.active = False
                    item.save(update_fields=("active",))
            row.version += 1
            row.save()
            _record(row, actor, "withdrawn", values["scope"])
            audit(event, actor, "gallery_consent_withdrawn", row, version=row.version)
            notice(event, "gallery_withdrawn", row.pk, row.version)
            return {"team_id": team_id, "version": row.version, **selection(row), "state": "withdrawn"}
        return command(event, actor, values, path=f"teams/{team_id}/gallery-consent/withdraw", run=run)
