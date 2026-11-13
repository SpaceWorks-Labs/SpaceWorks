"""Card Studio (decision 314/315): space-level card and certificate templates.

Depends on 0011 (the image adapter and cut-outs); re-chain this if another lane has since added a later leaf."""
import django.db.models.deletion
import django.db.models.functions.text
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("card_designs", "0011_image_adapter_cutouts"),
    ]

    operations = [
        migrations.CreateModel(
            name="CardTemplate",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=80)),
                ("description", models.CharField(blank=True, default="", max_length=200)),
                ("kind", models.CharField(choices=[("card", "Card"), ("certificate", "Certificate")], default="card",
                                          max_length=12)),
                ("domain_hint", models.CharField(blank=True, default="", max_length=16)),
                ("stock", models.CharField(max_length=24)),
                ("theme", models.CharField(default="light", max_length=5)),
                ("document", models.JSONField()),
                ("source_design_id", models.PositiveBigIntegerField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("makerspace", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                                 related_name="card_templates", to="makerspaces.makerspace")),
            ],
            options={"ordering": ["makerspace_id", "name", "pk"]},
        ),
        migrations.AddConstraint(
            model_name="cardtemplate",
            constraint=models.UniqueConstraint(django.db.models.functions.text.Lower("name"), models.F("makerspace"),
                                               name="uniq_card_template_name"),
        ),
    ]
