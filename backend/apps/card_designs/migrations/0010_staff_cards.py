"""O-B4 part 2: staff ID cards -- the `StaffCard` holder kind, its number scheme and the `staff_cards` domain.

The four holder-keyed tables (verify token, sensitive extras, photo request, wallet pass) gain a nullable
`staff_card` FK, and their "exactly one holder" / "one per holder" constraints are rebuilt for four kinds.
Existing rows are unaffected (every one already names exactly one of the other three).
"""
import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models
from django.db.models import Q

from apps.card_designs.models_holders import exactly_one_holder

HOLDER_TABLES = (
    ("cardverifytoken", "card_verify_token_one_holder", "uniq_live_verify_token", Q(retired_at__isnull=True)),
    ("cardholderextras", "card_extras_one_holder", "uniq_card_extras", None),
    ("cardphotorequest", "card_photo_request_one_holder", "uniq_open_photo_request", Q(resolved_at__isnull=True)),
)


def _holder_operations():
    ops = []
    for model, check, prefix, condition in HOLDER_TABLES:
        ops.append(migrations.AddField(model, "staff_card", models.ForeignKey(
            blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="+",
            to="card_designs.staffcard")))
        ops.append(migrations.RemoveConstraint(model, check))
        ops.append(migrations.AddConstraint(model, exactly_one_holder(check)))
        clause = Q(staff_card__isnull=False)
        if condition is not None:
            clause &= condition
        ops.append(migrations.AddConstraint(model, models.UniqueConstraint(
            fields=["staff_card"], condition=clause, name=f"{prefix}_staff_card")))
    ops.append(migrations.AddField("walletpass", "staff_card", models.ForeignKey(
        blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="+",
        to="card_designs.staffcard")))
    ops.append(migrations.RemoveConstraint("walletpass", "wallet_pass_one_holder"))
    ops.append(migrations.AddConstraint("walletpass", exactly_one_holder("wallet_pass_one_holder")))
    ops.append(migrations.AddConstraint("walletpass", models.UniqueConstraint(
        fields=["staff_card", "platform"], condition=Q(staff_card__isnull=False), name="uniq_wallet_pass_staff_card")))
    return ops


class Migration(migrations.Migration):
    dependencies = [
        ("card_designs", "0009_event_badge_roles"),
        ("makerspaces", "0150_space_email_sender_verification"),
    ]

    operations = [
        migrations.CreateModel(
            name="StaffCard",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("card_number", models.PositiveIntegerField()),
                ("number_text", models.CharField(blank=True, default="", max_length=32)),
                ("roles", models.JSONField(blank=True, default=list)),
                ("print_count", models.PositiveIntegerField(default=0)),
                ("last_printed_at", models.DateTimeField(blank=True, null=True)),
                ("issued_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                ("revoked_reason", models.CharField(blank=True, default="", max_length=32)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("makerspace", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                                 related_name="staff_cards", to="makerspaces.makerspace")),
                ("membership", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                                 related_name="staff_cards", to="makerspaces.makerspacemembership")),
            ],
            options={"ordering": ["makerspace_id", "-issued_at", "-pk"]},
        ),
        migrations.AddConstraint("staffcard", models.UniqueConstraint(
            fields=["makerspace", "card_number"], name="uniq_staff_card_number")),
        migrations.AddConstraint("staffcard", models.UniqueConstraint(
            fields=["membership"], condition=Q(revoked_at__isnull=True, membership__isnull=False),
            name="uniq_live_staff_card_per_membership")),
        migrations.AddConstraint("staffcard", models.UniqueConstraint(
            fields=["makerspace", "number_text"], condition=~Q(number_text=""), name="uniq_staff_card_number_text")),
        migrations.CreateModel(
            name="StaffCardNumbering",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("prefix", models.CharField(blank=True, default="", max_length=6)),
                ("pattern", models.CharField(blank=True, default="", max_length=40)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("makerspace", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="+",
                                                    to="makerspaces.makerspace")),
            ],
        ),
        *_holder_operations(),
        migrations.AlterField("carddesign", "domain", models.CharField(max_length=16, choices=[
            ("member_cards", "Member cards"), ("id_programme", "ID programme cards"),
            ("event_card", "Event ID cards"), ("event_ticket", "Event tickets"), ("staff_cards", "Staff ID cards")])),
        migrations.RemoveConstraint("carddesign", "card_design_domain_targets"),
        migrations.AddConstraint("carddesign", models.CheckConstraint(name="card_design_domain_targets", condition=(
            Q(domain="member_cards", programme__isnull=True, event__isnull=True, ticket_type__isnull=True)
            & ~Q(plan__isnull=False, title__isnull=False)
            & (Q(organization__isnull=True) | Q(plan__isnull=True, title__isnull=True))
            | Q(domain="id_programme", programme__isnull=False, plan__isnull=True, title__isnull=True,
                organization__isnull=True, event__isnull=True, ticket_type__isnull=True)
            | Q(domain__in=["event_card", "event_ticket"], plan__isnull=True, title__isnull=True,
                programme__isnull=True) & (Q(ticket_type__isnull=True) | Q(event__isnull=False))
            | Q(domain="staff_cards", plan__isnull=True, title__isnull=True, programme__isnull=True,
                organization__isnull=True, event__isnull=True, ticket_type__isnull=True)
        ))),
    ]
