"""Private object keys owned by a space's card rows (release 2 L3), for purge and moves.

Canonical: design artwork and programme/event card photos. Coordination only (purge):
staged uploads behind them and temporary job results, which never travel.
"""


def collect_card_keys(makerspace, add, *, include_coordination=True):
    from apps.card_designs.models import CardDesignAsset, CardJob
    from apps.events.models import EventIdCard
    from apps.id_programmes.models import IdProgrammeCard

    for key in CardDesignAsset.objects.filter(makerspace=makerspace).values_list("object_key", flat=True):
        add(key)
        if include_coordination:
            add(f"staging/{key}")
    for model in (IdProgrammeCard, EventIdCard):
        for key in model.objects.filter(makerspace=makerspace).exclude(photo_object_key="").values_list(
                "photo_object_key", flat=True):
            add(key)
    if include_coordination:
        for job in CardJob.objects.filter(makerspace=makerspace).only("result_key", "parts"):
            add(job.result_key)
            for key in job.parts or ():
                add(key)
