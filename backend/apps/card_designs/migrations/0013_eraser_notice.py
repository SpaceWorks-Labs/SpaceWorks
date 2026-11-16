"""Decision 345(b): the background-eraser notice version on each cut-out request, and a photo owner's opt-out as its
own small model (it travels with the space and is in the member's own data export; `CardHolderExtras` stays omitted).

Chains off 0012 (re-chain if another lane adds a later leaf)."""
import django.db.models.deletion
from django.db import migrations, models
from django.db.models import Q

from apps.card_designs.models_holders import exactly_one_holder

HOLDER_FIELDS = ("member_card", "programme_card", "event_card", "staff_card")
HOLDER_TARGETS = {"member_card": "makerspaces.membercard", "programme_card": "id_programmes.idprogrammecard",
                  "event_card": "events.eventidcard", "staff_card": "card_designs.staffcard"}


class Migration(migrations.Migration):
    dependencies = [
        ("card_designs", "0012_card_templates"),
    ]

    operations = [
        migrations.AddField(model_name="cardphotocutout", name="notice_version",
                            field=models.CharField(blank=True, default="", max_length=16)),
        migrations.CreateModel(
            name="CardPhotoEraserOptOut",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("makerspace", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="+",
                                                 to="makerspaces.makerspace")),
                *[(name, models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE,
                                           related_name="+", to=HOLDER_TARGETS[name])) for name in HOLDER_FIELDS],
                ("opted_out_at", models.DateTimeField(auto_now_add=True)),
                ("notice_version", models.CharField(blank=True, default="", max_length=16)),
            ],
        ),
        migrations.AddConstraint("cardphotoeraseroptout", exactly_one_holder("card_eraser_opt_out_one_holder")),
        *[migrations.AddConstraint("cardphotoeraseroptout", models.UniqueConstraint(
            fields=[name], condition=Q(**{f"{name}__isnull": False}), name=f"uniq_card_eraser_opt_out_{name}"))
          for name in HOLDER_FIELDS],
    ]
