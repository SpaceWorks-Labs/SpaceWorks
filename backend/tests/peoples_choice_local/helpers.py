"""A hackathon with a live public gallery for People's choice tests (#181 S3)."""

from datetime import timedelta
from uuid import uuid4

from django.utils import timezone

from apps.events.judging.models_peoples_choice import PeoplesChoiceConfig
from apps.events.submissions.gallery_models import GalleryConsent, GalleryEntry, GalleryPublication
from apps.events.submissions.models_projects import SubmissionSnapshot
from tests.events.pairwise_helpers import command, pairwise_world
from tests.events.ticketing_helpers import account

FEATURES = ("events.project_gallery", "events.peoples_choice")


def enable(world, *keys):
    world.space.enabled_features = sorted(set(world.space.enabled_features) | set(keys))
    world.space.save(update_fields=["enabled_features"])


def disable(world, *keys):
    world.space.enabled_features = sorted(set(world.space.enabled_features) - set(keys))
    world.space.save(update_fields=["enabled_features"])


def gallery_world(settings, monkeypatch, projects=3):
    """Every project is a live, consented public gallery entry; the award is not configured yet."""
    world = pairwise_world(settings, monkeypatch, projects=projects, judges=0, enabled=False)
    enable(world, *FEATURES)
    publication = GalleryPublication.objects.create(event=world.event, published_at=timezone.now(), active=True,
                                                    published_by=world.manager)
    world.entries = []
    for pk in world.snapshots:
        snap = world.ports.snaps[pk]
        row = SubmissionSnapshot.objects.select_related("submission").get(pk=pk)
        GalleryConsent.objects.create(event=world.event, team_id=row.submission.team_id, snapshot_id=pk,
                                      metadata_public=True, metadata_generation=1)
        world.entries.append(GalleryEntry.objects.create(event=world.event, publication=publication, snapshot_id=pk,
                                                         title=snap.title, description="", metadata_generation=1))
    world.voters = [account(f"voter-{uuid4().hex[:10]}") for _ in range(4)]
    return world


def configure(world, **fields):
    """Switch the award on through the workflow (open now, unless a window is given)."""
    from apps.events.judging import peoples_choice
    row = PeoplesChoiceConfig.objects.filter(event=world.event).first()
    return peoples_choice.update(world.event.pk, actor=world.manager,
                                 data=command(row.version if row else 0, **{"enabled": True, **fields}))


def vote(world, voter, entry, version=0):
    from apps.events.judging import peoples_choice_votes
    return peoples_choice_votes.cast(world.event.pk, actor=voter, data=command(version, entry_public_id=str(entry.public_id)))


def close_voting(world):
    """Move the window into the past without the workflow (it refuses no closing time, only bad order)."""
    now = timezone.now()
    PeoplesChoiceConfig.objects.filter(event=world.event).update(opens_at=now - timedelta(hours=2),
                                                                 closes_at=now - timedelta(minutes=1))


def config_version(world):
    return PeoplesChoiceConfig.objects.get(event=world.event).version
