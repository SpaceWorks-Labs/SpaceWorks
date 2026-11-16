from django.db import migrations, models
from django.db.models import F, Q


class Migration(migrations.Migration):
    dependencies = [("events", "0030_certificate_templates"), ("makerspaces", "0090_website_embedding")]
    operations = [
        migrations.CreateModel(name='EventPage', fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ('makerspace', models.ForeignKey('makerspaces.Makerspace', on_delete=models.CASCADE)),
            ('event', models.OneToOneField('events.Event', null=True, blank=True, on_delete=models.CASCADE, related_name='website_page')),
            ('series', models.OneToOneField('events.EventSeries', null=True, blank=True, on_delete=models.CASCADE, related_name='website_page')),
            ('released', models.BooleanField(default=False)),
            ('revision', models.PositiveIntegerField(default=1)),
            ('updated_at', models.DateTimeField(auto_now=True)),
        ], options={'constraints': [models.CheckConstraint(condition=Q(event__isnull=False, series__isnull=True) | Q(event__isnull=True, series__isnull=False), name='event_page_exact_owner')]}),
        migrations.CreateModel(name='EventPageAsset', fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ('page', models.ForeignKey('events.eventpage', on_delete=models.CASCADE, related_name='assets')),
            ('object_key', models.CharField(max_length=300, unique=True)),
            ('size_bytes', models.PositiveIntegerField()),
            ('alt_text', models.CharField(max_length=200)),
            ('created_at', models.DateTimeField(auto_now_add=True)),
        ], options={}),
        migrations.CreateModel(name='EventPageSection', fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ('page', models.ForeignKey('events.eventpage', on_delete=models.CASCADE, related_name='sections')),
            ('kind', models.CharField(max_length=16, choices=[('intro', 'Introduction'), ('logo', 'Page logo'), ('speaker', 'Speaker'), ('track', 'Track'), ('room', 'Room'), ('sponsor', 'Sponsor'), ('faq', 'FAQ'), ('resource', 'Resource')])),
            ('slug', models.SlugField(max_length=80)),
            ('title', models.CharField(max_length=200)),
            ('body', models.CharField(max_length=10000, blank=True)),
            ('url', models.URLField(max_length=500, blank=True)),
            ('asset', models.ForeignKey('events.eventpageasset', on_delete=models.SET_NULL, null=True, blank=True)),
            ('visibility', models.CharField(max_length=12, choices=(('draft', 'Draft'), ('published', 'Published')), default='draft')),
            ('position', models.PositiveIntegerField(default=0)),
        ], options={'ordering': ('position', 'id'), 'constraints': [models.UniqueConstraint(fields=('page', 'slug'), name='event_section_page_slug')]}),
        migrations.CreateModel(name='EventSession', fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ('page', models.ForeignKey('events.eventpage', on_delete=models.CASCADE, related_name='sessions')),
            ('slug', models.SlugField(max_length=80)),
            ('title', models.CharField(max_length=200)),
            ('body', models.CharField(max_length=10000, blank=True)),
            ('starts_at', models.DateTimeField()),
            ('ends_at', models.DateTimeField()),
            ('track', models.ForeignKey('events.eventpagesection', on_delete=models.RESTRICT, null=True, blank=True, related_name='track_sessions')),
            ('room', models.ForeignKey('events.eventpagesection', on_delete=models.RESTRICT, null=True, blank=True, related_name='room_sessions')),
            ('delay_minutes', models.PositiveIntegerField(default=0)),
            ('visibility', models.CharField(max_length=12, choices=(('draft', 'Draft'), ('published', 'Published')), default='draft')),
        ], options={'ordering': ('starts_at', 'id'), 'constraints': [models.UniqueConstraint(fields=('page', 'slug'), name='event_session_page_slug'), models.CheckConstraint(condition=Q(ends_at__gt=F('starts_at')), name='event_session_positive_window'), models.CheckConstraint(condition=Q(delay_minutes__lte=1440), name='event_session_delay_bound')]}),
        migrations.CreateModel(name='EventSessionSpeaker', fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ('session', models.ForeignKey('events.eventsession', on_delete=models.CASCADE, related_name='speaker_links')),
            ('speaker', models.ForeignKey('events.eventpagesection', on_delete=models.RESTRICT, related_name='session_links')),
        ], options={'constraints': [models.UniqueConstraint(fields=('session', 'speaker'), name='event_session_speaker_unique')]}),
    ]
