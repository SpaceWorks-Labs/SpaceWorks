"""Public profile contract; existing directory profiles remain unpublished."""
from django.conf import settings
from django.db import migrations, models
from django.core.validators import RegexValidator
from django.db.models.functions import Lower

HANDLE_PATTERN = '^[a-z0-9](?:[a-z0-9._-]{1,28}[a-z0-9])$'

class Migration(migrations.Migration):
    dependencies = [("makerspaces", "0093_fixed_roles_constraint"), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]

    operations = [
        migrations.AddField(model_name='memberprofile', name='public_visible', field=models.BooleanField(default=False)),
        migrations.AddField(model_name='memberprofile', name='public_consented_at', field=models.DateTimeField(null=True, blank=True, editable=False)),
        migrations.AddField(model_name='memberprofile', name='show_activity_graph', field=models.BooleanField(default=False)),
        migrations.AddField(model_name='memberprofile', name='show_events', field=models.BooleanField(default=False)),
        migrations.AddField(model_name='memberprofile', name='show_speaking', field=models.BooleanField(default=False)),
        migrations.AddField(model_name='memberprofile', name='show_projects', field=models.BooleanField(default=False)),
        migrations.AddField(model_name='memberprofile', name='show_machine_activity', field=models.BooleanField(default=False)),
        migrations.AddField(model_name='memberprofile', name='show_bookings', field=models.BooleanField(default=False)),
        migrations.AddField(model_name='memberprofile', name='show_loans', field=models.BooleanField(default=False)),
        migrations.AddField(model_name='memberprofile', name='domains', field=models.JSONField(default=list, blank=True)),
        migrations.AddField(model_name='memberprofile', name='skills', field=models.JSONField(default=list, blank=True)),
        migrations.AddField(model_name='memberprofile', name='links', field=models.JSONField(default=list, blank=True)),
        migrations.AddField(model_name='memberproject', name='subtitle', field=models.CharField(max_length=200, blank=True, default='')),
        migrations.AddField(model_name='memberproject', name='tags', field=models.JSONField(default=list, blank=True)),
        migrations.AddField(model_name='memberproject', name='public_visible', field=models.BooleanField(default=False)),
        migrations.CreateModel(
            name='PublicHandle',
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ('user', models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='public_handle')),
                ('profile', models.ForeignKey("makerspaces.memberprofile", on_delete=models.CASCADE, related_name='handles')),
                ('handle', models.CharField(max_length=30, validators=[RegexValidator(HANDLE_PATTERN)])),
                ('claimed_at', models.DateTimeField(auto_now_add=True)),
                ('changed_at', models.DateTimeField())
            ],
            options={'constraints': [models.UniqueConstraint(Lower('handle'), name='public_handle_ci_unique'), models.CheckConstraint(condition=models.Q(handle__regex=HANDLE_PATTERN), name='public_handle_grammar')]},
        ),
        migrations.CreateModel(
            name='PublicHandleRedirect',
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ('profile', models.ForeignKey("makerspaces.memberprofile", on_delete=models.CASCADE, related_name='handle_redirects')),
                ('handle', models.CharField(max_length=30)),
                ('released_at', models.DateTimeField()),
                ('expires_at', models.DateTimeField(db_index=True))
            ],
            options={'constraints': [models.UniqueConstraint(Lower('handle'), name='profile_redirect_ci_unique')]},
        ),
        migrations.CreateModel(
            name='ProfileTimelineEntry',
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ('profile', models.ForeignKey("makerspaces.memberprofile", on_delete=models.CASCADE, related_name='timeline')),
                ('kind', models.CharField(max_length=16, choices=[("experience", "Experience"), ("education", "Education"), ("volunteering", "Volunteering")])),
                ('title', models.CharField(max_length=200)),
                ('organization', models.CharField(max_length=200, blank=True, default='')),
                ('location', models.CharField(max_length=200, blank=True, default='')),
                ('start', models.DateField()),
                ('end', models.DateField(null=True, blank=True)),
                ('description', models.TextField(blank=True, default='')),
                ('order', models.PositiveSmallIntegerField(default=0))
            ],
            options={'ordering': ('order', '-start', 'id'), 'constraints': [models.CheckConstraint(condition=models.Q(end__isnull=True) | models.Q(end__gte=models.F('start')), name='profile_timeline_date_order')]},
        ),
    ]
