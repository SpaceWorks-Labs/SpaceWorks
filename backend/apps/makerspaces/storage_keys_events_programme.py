"""Retained tenant object locators; account vault and foreign profile bytes stay independent."""
from django.apps import apps


def collect_programme_keys(makerspace, add, *, include_coordination=True):
    for label in ("events.SubmissionAsset", "events.HackathonParticipantAsset"):
        rows = apps.get_model(label).objects.filter(event__makerspace=makerspace)
        fields = ("object_key", "staging_key", "verification_key") if include_coordination else ("object_key",)
        if not include_coordination:
            rows = rows.filter(state="ready")
        for values in rows.values_list(*fields).iterator(chunk_size=500):
            for key in values:
                add(key)
    library = apps.get_model("events.EventCertificateLibraryArtwork").objects.filter(
        template__makerspace=makerspace,
    )
    if not include_coordination:
        library = library.filter(promoted_at__isnull=False)
    for key in library.values_list("object_key", flat=True).iterator(chunk_size=500):
        add(key)
        if include_coordination:
            add(f"staging/{key}")
    if include_coordination:
        for label, owner in (("events.BadgePrintJob", "event__makerspace"),
                             ("events.BadgePrintResource", "job__event__makerspace")):
            for key in apps.get_model(label).objects.filter(**{owner: makerspace}).values_list("object_key", flat=True):
                add(key)
