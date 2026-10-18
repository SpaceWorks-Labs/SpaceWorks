"""Event-owned lifecycle cleanup; history pins assets until whole-owner removal."""

from datetime import timedelta
from django.db import transaction
from django.utils import timezone
from apps.audit.services import record
from apps.makerspaces import website_assets
from apps.makerspaces.website_asset_journal import schedule
from apps.makerspaces.public_page_asset_cleanup import clean_object
from .models_website import EventPage


def schedule_page_cleanup(page):
    """Call before deleting an owned page graph, inside its deletion transaction."""
    for asset in page.assets.all():
        if not website_assets.owns(asset.object_key, "events", page.makerspace_id, page.pk, asset=asset):
            continue
        job_id = schedule(asset)
        transaction.on_commit(lambda pk=job_id: clean_object(pk), robust=True)


@transaction.atomic
def collect_unattached(page_id):
    from apps.tenant_migration.gate_runtime import assert_write_allowed
    from .models import Event, EventSeries
    initial = EventPage.objects.filter(pk=page_id).first()
    if initial is None:
        return 0
    assert_write_allowed(initial.makerspace_id)
    # Same order as website mutations: series -> occurrence -> tenant -> page.
    series_id = initial.series_id
    if initial.event_id:
        series_id = Event.objects.values_list("series_id", flat=True).get(pk=initial.event_id)
    if series_id:
        EventSeries.objects.select_for_update().get(pk=series_id)
    if initial.event_id:
        Event.objects.select_for_update().get(pk=initial.event_id)
    from apps.makerspaces.models import Makerspace
    Makerspace.objects.select_for_update().get(pk=initial.makerspace_id)
    page = EventPage.objects.select_for_update().filter(pk=page_id).first()
    if page is None:
        return 0
    removed = 0
    eligible = page.assets.filter(created_at__lte=timezone.now() - timedelta(hours=24),
                                 eventpagerevisionasset__isnull=True, eventpagesection__isnull=True)
    for asset in eligible.order_by("pk")[:50]:
        if not website_assets.owns(asset.object_key, "events", page.makerspace_id, page.pk, asset=asset):
            continue
        job_id = schedule(asset)
        asset.delete()
        transaction.on_commit(lambda pk=job_id: clean_object(pk), robust=True)
        removed += 1
    if removed:
        from .services_website import bump
        bump(page)
        record(None, "event.website_unattached_assets_removed", makerspace=page.makerspace,
               target=page, meta={"count": removed, "revision": page.revision})
    return removed
