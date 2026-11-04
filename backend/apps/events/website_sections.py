"""Keep account-credit anchors stable while replacing the working document."""

from rest_framework.exceptions import ValidationError
from .models_website import EventPageSection


def reconcile_sections(page, rows):
    existing = {row.slug: row for row in page.sections.select_for_update()}
    wanted = {row["slug"] for row in rows}
    for slug, section in existing.items():
        if slug not in wanted:
            if section.speaker_identities.exists():
                section.is_working = False
                section.save(update_fields=["is_working"])
            else:
                section.delete()
    result = {}
    for values in rows:
        section = existing.get(values["slug"])
        if section is not None:
            if values["kind"] != section.kind and section.speaker_identities.exists():
                raise ValidationError({"sections": "An account-linked speaker slug cannot change kind."})
            for key, value in values.items():
                setattr(section, key, value)
            section.is_working = True
            section.save(update_fields=[*values, "is_working"])
        else:
            section = EventPageSection.objects.create(page=page, **values)
        result[section.slug] = section
    return result
