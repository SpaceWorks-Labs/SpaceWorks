"""Unified accounts A+1: the schema for one account per person.

Refuses first, before any schema change, when live staff accounts exist and
``ACCOUNT_UNIFICATION_ACK`` is not the reviewed report's ``plan_sha256``. The new account
context check is added NOT VALID here and validated by 0050 after the conversion.
"""

import uuid

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.contrib.postgres.operations import AddConstraintNotValid
from django.db import migrations, models

from ._0049_unified_guards import SQL, reverse_sql


def require_acknowledged_plan(apps, schema_editor):
    from apps.accounts.unification_plan import assert_acknowledged

    assert_acknowledged(schema_editor.connection, getattr(settings, "ACCOUNT_UNIFICATION_ACK", ""))


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0048_remove_b1_guard_branch"),
        ("auth", "0012_alter_user_first_name_max_length"),
        ("makerspaces", "0114_membership_track"),
    ]

    operations = [
        migrations.RunPython(require_acknowledged_plan, migrations.RunPython.noop),
        migrations.CreateModel(
            name="AccountMergeIntent",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("method", models.CharField(choices=[("credentials", "Password and second factor"), ("email_codes", "Two emailed codes")], max_length=16)),
                ("identifier_digest", models.CharField(max_length=64)),
                ("survivor_code_digest", models.CharField(blank=True, max_length=64)),
                ("source_code_digest", models.CharField(blank=True, max_length=64)),
                ("survivor_code_verified_at", models.DateTimeField(blank=True, null=True)),
                ("source_code_verified_at", models.DateTimeField(blank=True, null=True)),
                ("sent_at", models.DateTimeField(blank=True, null=True)),
                ("attempts", models.PositiveSmallIntegerField(default=0)),
                ("resends", models.PositiveSmallIntegerField(default=0)),
                ("proved_at", models.DateTimeField(blank=True, null=True)),
                ("preview_sha256", models.CharField(blank=True, max_length=64)),
                ("state", models.CharField(choices=[("started", "Started"), ("proved", "Proved"), ("consumed", "Consumed"), ("cancelled", "Cancelled"), ("expired", "Expired")], default="started", max_length=16)),
                ("expires_at", models.DateTimeField()),
                ("consumed_at", models.DateTimeField(blank=True, null=True)),
                ("cancelled_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name="AccountMergeRecord",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("decision", models.CharField(choices=[("converted", "Converted"), ("merged", "Merged")], max_length=16)),
                ("proof_method", models.CharField(choices=[("migration", "Unification migration"), ("credentials", "Password and second factor"), ("email_codes", "Two emailed codes")], max_length=16)),
                ("run_id", models.UUIDField()),
                ("plan_sha256", models.CharField(blank=True, max_length=64)),
                ("snapshot_scheme", models.CharField(choices=[("deployment", "Deployment field key"), ("account", "Per-account key"), ("scrubbed", "Scrubbed")], max_length=16)),
                ("snapshot_key_version", models.PositiveIntegerField(blank=True, null=True)),
                ("snapshot_ciphertext", models.TextField(blank=True)),
                ("held_fields", models.JSONField(blank=True, default=list)),
                ("roles_kept", models.JSONField(blank=True, default=list)),
                ("counts", models.JSONField(blank=True, default=dict)),
                ("state", models.CharField(choices=[("pending", "Pending"), ("completed", "Completed")], default="pending", max_length=16)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
            ],
        ),
        migrations.RemoveConstraint(model_name="user", name="user_account_context"),
        migrations.AddField(
            model_name="user", name="merged_at", field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="user",
            name="merged_into",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="merged_shells", to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name="user",
            name="account_kind",
            field=models.CharField(choices=[("member", "Person"), ("staff", "Inert shell"), ("platform", "Platform")], default="member", max_length=16),
        ),
        AddConstraintNotValid(
            model_name="user",
            constraint=models.CheckConstraint(condition=models.Q(models.Q(("account_kind", "staff"), ("is_active", False), ("staff_makerspace__isnull", True), models.Q(("retired_at__isnull", False), ("merged_into__isnull", False), _connector="OR")), models.Q(("account_kind__in", ["member", "platform"]), ("merged_into__isnull", True), ("retired_at__isnull", True), ("staff_makerspace__isnull", True)), _connector="OR"), name="user_account_context"),
        ),
        migrations.AddConstraint(
            model_name="user",
            constraint=models.CheckConstraint(condition=models.Q(models.Q(("merged_at__isnull", True), ("merged_into__isnull", True)), models.Q(("merged_at__isnull", False), ("merged_into__isnull", False)), _connector="OR"), name="user_merge_stamp"),
        ),
        migrations.AddConstraint(
            model_name="user",
            constraint=models.CheckConstraint(condition=models.Q(("merged_into", models.F("id")), _negated=True), name="user_not_merged_into_self"),
        ),
        migrations.AddField(
            model_name="accountmergeintent",
            name="source",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="account_merge_intents_as_source", to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name="accountmergeintent",
            name="survivor",
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="account_merge_intents", to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name="accountmergerecord",
            name="source",
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="merge_records_as_source", to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name="accountmergerecord",
            name="target",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="merge_records_as_target", to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddIndex(
            model_name="accountmergeintent",
            index=models.Index(fields=["survivor", "state"], name="merge_intent_survivor_idx"),
        ),
        migrations.AddConstraint(
            model_name="accountmergeintent",
            constraint=models.CheckConstraint(condition=models.Q(("source", models.F("survivor")), _negated=True), name="merge_intent_distinct_accounts"),
        ),
        migrations.AddConstraint(
            model_name="accountmergerecord",
            constraint=models.CheckConstraint(condition=models.Q(models.Q(("decision", "converted"), ("proof_method", "migration"), ("target__isnull", True)), models.Q(("decision", "merged"), ("proof_method__in", ["credentials", "email_codes"]), ("target__isnull", False), models.Q(("target", models.F("source")), _negated=True)), _connector="OR"), name="merge_record_decision_shape"),
        ),
        migrations.AddConstraint(
            model_name="accountmergerecord",
            constraint=models.CheckConstraint(condition=models.Q(models.Q(("completed_at__isnull", True), ("state", "pending")), models.Q(("completed_at__isnull", False), ("state", "completed")), _connector="OR"), name="merge_record_completion"),
        ),
        migrations.AddConstraint(
            model_name="accountmergerecord",
            constraint=models.CheckConstraint(condition=models.Q(models.Q(("snapshot_ciphertext", ""), ("snapshot_scheme", "scrubbed")), models.Q(models.Q(("snapshot_scheme", "scrubbed"), _negated=True), models.Q(("snapshot_ciphertext", ""), _negated=True)), _connector="OR"), name="merge_record_snapshot_present"),
        ),
        migrations.AddConstraint(
            model_name="accountmergerecord",
            constraint=models.UniqueConstraint(condition=models.Q(("decision", "converted")), fields=("source",), name="uniq_merge_record_conversion"),
        ),
        migrations.AddConstraint(
            model_name="accountmergerecord",
            constraint=models.UniqueConstraint(condition=models.Q(("decision", "merged"), ("state", "completed")), fields=("source",), name="uniq_merge_record_completed_merge"),
        ),
        migrations.RunSQL(SQL, reverse_sql()),
    ]
