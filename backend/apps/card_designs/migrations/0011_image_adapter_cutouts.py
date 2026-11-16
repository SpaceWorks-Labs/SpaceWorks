"""Decision 314(c): the image-adapter provider settings, derived card-photo cut-outs and bulk photo batches."""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from django.db.models import Q

from apps.card_designs.models_holders import exactly_one_holder

HOLDER_FIELDS = ("member_card", "programme_card", "event_card", "staff_card")
HOLDER_TARGETS = {"member_card": "makerspaces.membercard", "programme_card": "id_programmes.idprogrammecard",
                  "event_card": "events.eventidcard", "staff_card": "card_designs.staffcard"}


def _adapter_fields():
    return [
        ("provider_url", models.CharField(blank=True, default="", max_length=300)),
        ("secret", models.TextField(blank=True, default="")),
        ("secret_fingerprint", models.CharField(blank=True, default="", max_length=12)),
        ("last_test_at", models.DateTimeField(blank=True, null=True)),
        ("last_test_ok", models.BooleanField(blank=True, null=True)),
        ("last_test_error", models.CharField(blank=True, default="", max_length=40)),
        ("updated_at", models.DateTimeField(auto_now=True)),
    ]


def _holder_fk_fields():
    fields = [("makerspace", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="+",
                                               to="makerspaces.makerspace"))]
    for name in HOLDER_FIELDS:
        fields.append((name, models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE,
                                               related_name="+", to=HOLDER_TARGETS[name])))
    return fields


class Migration(migrations.Migration):

    dependencies = [
        ("card_designs", "0010_staff_cards"),
        ("makerspaces", "0150_space_email_sender_verification"),
        ("events", "0063_l3_event_id_cards"),
        ("id_programmes", "0003_programme_archived_at"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="PlatformImageAdapter",
            fields=[("id", models.PositiveSmallIntegerField(default=1, editable=False, primary_key=True,
                                                            serialize=False)), *_adapter_fields()],
            options={"verbose_name_plural": "platform image adapter"},
        ),
        migrations.CreateModel(
            name="MakerspaceImageAdapter",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                *_adapter_fields(),
                ("use_platform_provider", models.BooleanField(default=True)),
                ("makerspace", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE,
                                                    related_name="image_adapter", to="makerspaces.makerspace")),
            ],
            options={"verbose_name_plural": "makerspace image adapters"},
        ),
        migrations.CreateModel(
            name="CardPhotoCutout",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("state", models.CharField(choices=[("queued", "Queued"), ("running", "Running"), ("done", "Ready"),
                                                    ("failed", "Failed")], default="queued", max_length=8)),
                ("error_code", models.CharField(blank=True, default="", max_length=32)),
                ("attempts", models.PositiveSmallIntegerField(default=0)),
                ("source_key", models.CharField(max_length=300)),
                ("cutout_key", models.CharField(blank=True, default="", max_length=300)),
                ("content_type", models.CharField(blank=True, default="", max_length=32)),
                ("size_bytes", models.PositiveBigIntegerField(default=0)),
                ("width", models.PositiveIntegerField(default=0)),
                ("height", models.PositiveIntegerField(default=0)),
                ("use_cutout", models.BooleanField(default=False)),
                ("provider_scope", models.CharField(blank=True, default="", max_length=8)),
                ("by_holder", models.BooleanField(default=False)),
                ("consent_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                *_holder_fk_fields(),
                ("requested_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                                   related_name="+", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddIndex("cardphotocutout", models.Index(fields=["state", "updated_at"],
                                                            name="cutout_state_updated_idx")),
        migrations.AddConstraint("cardphotocutout", exactly_one_holder("card_photo_cutout_one_holder")),
        *[migrations.AddConstraint("cardphotocutout", models.UniqueConstraint(
            fields=[name], condition=Q(**{f"{name}__isnull": False}), name=f"uniq_photo_cutout_{name}"))
          for name in HOLDER_FIELDS],
        migrations.CreateModel(
            name="CardPhotoBatch",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("kind", models.CharField(max_length=12)),
                ("event_id", models.PositiveBigIntegerField(blank=True, null=True)),
                ("state", models.CharField(choices=[("draft", "Reviewing"), ("applying", "Applying"),
                                                    ("done", "Finished"), ("cancelled", "Cancelled")],
                                           default="draft", max_length=10)),
                ("remove_backgrounds", models.BooleanField(default=False)),
                ("holders_consented", models.BooleanField(default=False)),
                ("file_count", models.PositiveIntegerField(default=0)),
                ("applied_count", models.PositiveIntegerField(default=0)),
                ("skipped_count", models.PositiveIntegerField(default=0)),
                ("failed_count", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("applied_at", models.DateTimeField(blank=True, null=True)),
                ("expires_at", models.DateTimeField()),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                                 related_name="+", to=settings.AUTH_USER_MODEL)),
                ("makerspace", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="+",
                                                 to="makerspaces.makerspace")),
            ],
            options={"ordering": ["-created_at", "-pk"]},
        ),
        migrations.AddIndex("cardphotobatch", models.Index(fields=["expires_at"], name="photo_batch_expiry_idx")),
        migrations.CreateModel(
            name="CardPhotoBatchItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("position", models.PositiveIntegerField()),
                ("filename", models.CharField(max_length=200)),
                ("file_key", models.CharField(blank=True, default="", max_length=300)),
                ("size_bytes", models.PositiveBigIntegerField(default=0)),
                ("match_kind", models.CharField(blank=True, default="", max_length=8)),
                ("candidates", models.JSONField(blank=True, default=list)),
                ("holder_id", models.PositiveBigIntegerField(blank=True, null=True)),
                ("has_photo", models.BooleanField(default=False)),
                ("decision", models.CharField(choices=[("apply", "Apply"), ("replace", "Replace"), ("keep", "Keep"),
                                                       ("skip", "Skip")], default="apply", max_length=8)),
                ("state", models.CharField(choices=[("pending", "Pending"), ("applied", "Applied"),
                                                    ("skipped", "Skipped"), ("failed", "Failed")],
                                           default="pending", max_length=8)),
                ("error_code", models.CharField(blank=True, default="", max_length=32)),
                ("batch", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="items",
                                            to="card_designs.cardphotobatch")),
            ],
            options={"ordering": ["position"]},
        ),
        migrations.AddConstraint("cardphotobatchitem", models.UniqueConstraint(
            fields=["batch", "position"], name="uniq_photo_batch_position")),
    ]
