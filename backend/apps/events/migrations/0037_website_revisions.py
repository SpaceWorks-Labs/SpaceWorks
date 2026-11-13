"""Add typed snapshots and durable identities before switching website readers."""
import uuid
from django.conf import settings
from django.db import migrations, models
from apps.events.website_content import default_editorial_document


class Migration(migrations.Migration):
    dependencies = [('events', '0036_event_speakers'), ('makerspaces', '0100_public_pages'),
                    migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(name='EventSessionIdentity', fields=[
            ('id', models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
            ('page', models.ForeignKey('events.eventpage', on_delete=models.CASCADE, related_name='session_identities')),
        ]),
        migrations.CreateModel(name='EventSessionAlias', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('slug', models.SlugField(max_length=80)),
            ('page', models.ForeignKey('events.eventpage', on_delete=models.CASCADE, related_name='session_aliases')),
            ('identity', models.ForeignKey('events.eventsessionidentity', on_delete=models.CASCADE, related_name='aliases')),
        ], options={'constraints': [models.UniqueConstraint(fields=('page', 'slug'), name='event_session_alias_reserved')]}),
        migrations.AddField(model_name='eventsession', name='identity', field=models.OneToOneField(
            'events.eventsessionidentity', null=True, on_delete=models.RESTRICT, related_name='working_session')),
        migrations.AddField(model_name='eventpage', name='editorial_document', field=models.JSONField(default=default_editorial_document)),
        migrations.CreateModel(name='EventPageRevision', fields=[
            ('id', models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
            ('schema_version', models.PositiveSmallIntegerField(default=1)),
            ('source_anchor_start', models.DateTimeField()),
            ('document', models.JSONField()),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('created_by', models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')),
            ('page', models.ForeignKey('events.eventpage', on_delete=models.CASCADE, related_name='revisions')),
        ]),
        migrations.AddField(model_name='eventpage', name='draft_revision', field=models.ForeignKey(
            'events.eventpagerevision', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')),
        migrations.AddField(model_name='eventpage', name='published_revision', field=models.ForeignKey(
            'events.eventpagerevision', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')),
        migrations.CreateModel(name='EventPageRevisionAsset', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('slot', models.CharField(max_length=100)),
            ('revision', models.ForeignKey('events.eventpagerevision', on_delete=models.CASCADE, related_name='asset_references')),
            ('asset', models.ForeignKey('events.eventpageasset', on_delete=models.RESTRICT)),
        ], options={'constraints': [models.UniqueConstraint(fields=('revision', 'slot'), name='event_revision_asset_slot')]}),
        migrations.CreateModel(name='EventPageRevisionMember', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('slot', models.UUIDField()),
            ('revision', models.ForeignKey('events.eventpagerevision', on_delete=models.CASCADE, related_name='member_references')),
            ('profile', models.ForeignKey('makerspaces.memberprofile', null=True, on_delete=models.SET_NULL)),
        ], options={'constraints': [models.UniqueConstraint(fields=('revision', 'slot'), name='event_revision_member_slot')]}),
    ]
