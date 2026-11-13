"""O-B4: card number schemes + counters, and member-card designs may be an organisation default."""
import django.db.models.deletion
from django.db import migrations, models
from django.db.models import Q


def _targets(member):
    return (
        member
        | Q(domain="id_programme", programme__isnull=False, plan__isnull=True, title__isnull=True,
            organization__isnull=True, event__isnull=True, ticket_type__isnull=True)
        | Q(domain__in=["event_card", "event_ticket"], plan__isnull=True, title__isnull=True,
            programme__isnull=True) & (Q(ticket_type__isnull=True) | Q(event__isnull=False))
    )


OLD_MEMBER = (Q(domain="member_cards", programme__isnull=True, organization__isnull=True, event__isnull=True,
                ticket_type__isnull=True) & ~Q(plan__isnull=False, title__isnull=False))
NEW_MEMBER = (Q(domain="member_cards", programme__isnull=True, event__isnull=True, ticket_type__isnull=True)
              & ~Q(plan__isnull=False, title__isnull=False)
              & (Q(organization__isnull=True) | Q(plan__isnull=True, title__isnull=True)))


class Migration(migrations.Migration):
    dependencies = [
        ("card_designs", "0007_wallet_platform_switch"),
        ("makerspaces", "0145_member_card_number_text_verify_name"),
    ]

    operations = [
        migrations.CreateModel(
            name="CardNumberScheme",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("prefix", models.CharField(blank=True, default="", max_length=6)),
                ("pattern", models.CharField(blank=True, default="", max_length=40)),
                ("draft_prefix", models.CharField(blank=True, default="", max_length=6)),
                ("draft_pattern", models.CharField(blank=True, default="", max_length=40)),
                ("published_at", models.DateTimeField(blank=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("makerspace", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="+",
                                                 to="makerspaces.makerspace")),
                ("title", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE,
                                            related_name="+", to="makerspaces.membershiptitle")),
            ],
        ),
        migrations.CreateModel(
            name="CardNumberCounter",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("scheme_key", models.CharField(max_length=32)),
                ("year", models.PositiveSmallIntegerField(default=0)),
                ("next_value", models.PositiveIntegerField(default=1)),
                ("makerspace", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="+",
                                                 to="makerspaces.makerspace")),
            ],
        ),
        migrations.AddConstraint("cardnumberscheme", models.UniqueConstraint(
            fields=("makerspace",), condition=Q(title__isnull=True), name="uniq_card_number_scheme_space")),
        migrations.AddConstraint("cardnumberscheme", models.UniqueConstraint(
            fields=("makerspace", "title"), condition=Q(title__isnull=False), name="uniq_card_number_scheme_title")),
        migrations.AddConstraint("cardnumbercounter", models.UniqueConstraint(
            fields=("makerspace", "scheme_key", "year"), name="uniq_card_number_counter")),
        migrations.RemoveConstraint("carddesign", "card_design_domain_targets"),
        migrations.AddConstraint("carddesign", models.CheckConstraint(
            name="card_design_domain_targets", condition=_targets(NEW_MEMBER))),
    ]
