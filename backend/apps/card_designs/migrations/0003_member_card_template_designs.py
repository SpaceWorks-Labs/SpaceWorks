"""Convert each space's stored member-card template into a published Classic design,
and record auto-issue OFF for every space that existed before release 2 (Q3).

`branding_config["member_card_template"]` is left in place (it travels with branding
and is harmless); cards render from the design from now on.
"""
from django.db import migrations

BRANDING_KEY = "member_card_template"


def forwards(apps, schema_editor):
    from apps.card_designs.default_templates import classic
    from apps.card_designs.layout import normalize_document
    Makerspace = apps.get_model("makerspaces", "Makerspace")
    CardDesign = apps.get_model("card_designs", "CardDesign")
    CardDesignRevision = apps.get_model("card_designs", "CardDesignRevision")
    MemberCardSettings = apps.get_model("makerspaces", "MemberCardSettings")
    for space in Makerspace.objects.all().iterator():
        MemberCardSettings.objects.get_or_create(makerspace=space, defaults={"auto_issue": False})
        template = (space.branding_config or {}).get(BRANDING_KEY)
        if not isinstance(template, dict):
            continue
        if CardDesign.objects.filter(makerspace=space, domain="member_cards", plan__isnull=True,
                                     title__isnull=True).exists():
            continue
        document = classic("member_cards")
        front = document["front"]["layers"]
        if template.get("include_photo") is False:
            front[:] = [layer for layer in front if layer["kind"] != "photo"]
        if template.get("include_qr") is False:
            front[:] = [layer for layer in front if layer["kind"] != "desk_qr" and layer["name"] != "QR caption"]
        back_text = (template.get("back_text") or "").replace("{", "").replace("}", "").strip()
        if back_text:
            for layer in document["back"]["layers"]:
                if layer["name"] == "Footer note":
                    layer["text"] = back_text[:500]
        document = normalize_document(document, check_contrast=False)
        design = CardDesign.objects.create(makerspace=space, domain="member_cards", name="Space default",
                                           document=document, published_document=document, published_revision=1,
                                           status="published", revision=1)
        CardDesignRevision.objects.create(design=design, revision=1, document=document)


class Migration(migrations.Migration):
    dependencies = [
        ("card_designs", "0002_holder_links"),
        ("makerspaces", "0119_l3_member_cards"),
    ]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
