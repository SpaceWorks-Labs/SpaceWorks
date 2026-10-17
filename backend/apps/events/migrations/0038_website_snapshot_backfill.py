"""Preserve the currently released projection without changing legacy prose."""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from django.db import migrations, models

GROUPS = ["HERO", "ABOUT", "HIGHLIGHTS", "SCHEDULE", "SPEAKERS", "SPONSORS", "VENUE", "FAQ", "RESOURCES", "EDITORIAL"]
FIELDS = "kind slug title body url visibility position headline organization website_url linkedin_url x_url sponsor_tier icon".split()


def backfill(apps, schema_editor):
    from apps.makerspaces.public_page_markdown import rendering_policy
    alias = schema_editor.connection.alias
    Page = apps.get_model("events", "EventPage")
    Identity = apps.get_model("events", "EventSessionIdentity")
    Alias = apps.get_model("events", "EventSessionAlias")
    Session = apps.get_model("events", "EventSession")
    Revision = apps.get_model("events", "EventPageRevision")
    Ref = apps.get_model("events", "EventPageRevisionAsset")
    for page in Page.objects.using(alias).select_related("event", "series").iterator():
        editorial = {"schema_version": 1, "cover_mode": "inherit", "cover_asset_id": None,
                     "accent_choice": "inherit", "sections": []}
        sections = list(page.sections.using(alias).all())
        section_by_id = {row.pk: row for row in sections}
        section_rows, session_rows = [], []
        for row in sections:
            section_rows.append({**{key: getattr(row, key) for key in FIELDS}, "asset_id": row.asset_id,
                                 "body_rendering": rendering_policy(row.body)})
        for row in page.sessions.using(alias).prefetch_related("speaker_links").all():
            identity = Identity.objects.using(alias).create(page_id=page.pk)
            Alias.objects.using(alias).create(page_id=page.pk, identity=identity, slug=row.slug)
            Session.objects.using(alias).filter(pk=row.pk).update(identity=identity)
            session_rows.append({"session_id": str(identity.pk), "slug": row.slug, "title": row.title,
                "body": row.body, "body_rendering": rendering_policy(row.body),
                "starts_at": row.starts_at.isoformat(), "ends_at": row.ends_at.isoformat(),
                "track": section_by_id[row.track_id].slug if row.track_id else None,
                "room": section_by_id[row.room_id].slug if row.room_id else None,
                "speakers": [section_by_id[link.speaker_id].slug for link in row.speaker_links.all()],
                "visibility": row.visibility, "delay_minutes": row.delay_minutes})
        if page.event_id:
            anchor = page.event.starts_at
        else:
            series = page.series
            anchor = datetime.combine(series.dtstart_local_date, series.dtstart_local_time,
                                      tzinfo=ZoneInfo(series.recurrence_timezone)).astimezone(timezone.utc)
        order = list(page.section_order)
        if "EDITORIAL" not in order:
            order.append("EDITORIAL")
        enabled = {**page.section_enabled, "EDITORIAL": True}
        document = {"tagline": page.tagline, "accent_color": page.accent_color, "section_order": order,
                    "section_enabled": enabled, "venue": page.venue, "editorial_document": editorial,
                    "sections": section_rows, "sessions": session_rows}
        revision = Revision.objects.using(alias).create(page_id=page.pk, source_anchor_start=anchor, document=document)
        for row in sections:
            if row.asset_id:
                Ref.objects.using(alias).create(revision=revision, asset_id=row.asset_id, slot=f"section:{row.slug}")
        Page.objects.using(alias).filter(pk=page.pk).update(
            editorial_document=editorial, section_order=order, section_enabled=enabled,
            draft_revision=revision, published_revision=revision if page.released else None)


class Migration(migrations.Migration):
    dependencies = [("events", "0037_website_revisions")]
    operations = [migrations.RunPython(backfill, migrations.RunPython.noop),
                  migrations.AlterField(model_name="eventsession", name="identity", field=models.OneToOneField(
                      "events.eventsessionidentity", on_delete=models.RESTRICT, related_name="working_session"))]
