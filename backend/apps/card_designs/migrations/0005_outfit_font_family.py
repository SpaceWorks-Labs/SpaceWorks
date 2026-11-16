# Hand-written for owner decision 220(c): the designer's brand text face is a real `Outfit`
# family, so stored designs move from the legacy "Gilroy" token (which always printed in
# Outfit) to "Outfit" and the picker label matches the rendering.
#
# Only the mutable working copies move: `CardDesign.document` and `published_document`.
# `CardDesignRevision` is append-only history and keeps "Gilroy"; `fonts.canonical` reads it
# as Outfit, as it does for imports and tenant dumps made before this release.
#
# Reverse restores "Gilroy" only on Outfit 400-700 layers, the weights the old token carried;
# any other Outfit weight was a catalogue choice and stays.

from django.db import migrations

LEGACY, CURRENT = "Gilroy", "Outfit"
LEGACY_WEIGHTS = (400, 500, 600, 700)


def _rewrite(value, source, target, weights=None):
    """(new value, changed) with every `font_family == source` layer renamed to `target`."""
    if isinstance(value, list):
        rows = [_rewrite(item, source, target, weights) for item in value]
        return [row for row, _ in rows], any(changed for _, changed in rows)
    if not isinstance(value, dict):
        return value, False
    result, changed = {}, False
    for key, item in value.items():
        result[key], moved = _rewrite(item, source, target, weights)
        changed = changed or moved
    if result.get("font_family") == source and (weights is None or result.get("font_weight") in weights):
        result["font_family"], changed = target, True
    return result, changed


def _move(apps, source, target, weights=None):
    CardDesign = apps.get_model("card_designs", "CardDesign")
    for design in CardDesign.objects.only("pk", "document", "published_document").iterator():
        document, draft_changed = _rewrite(design.document, source, target, weights)
        published, published_changed = _rewrite(design.published_document, source, target, weights)
        if draft_changed or published_changed:
            # update(): no auto_now bump and no compare-and-swap revision churn.
            CardDesign.objects.filter(pk=design.pk).update(document=document, published_document=published)


def forwards(apps, schema_editor):
    _move(apps, LEGACY, CURRENT)


def backwards(apps, schema_editor):
    _move(apps, CURRENT, LEGACY, LEGACY_WEIGHTS)


class Migration(migrations.Migration):

    dependencies = [
        ('card_designs', '0004_card_design_archived_at'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards, elidable=False),
    ]
