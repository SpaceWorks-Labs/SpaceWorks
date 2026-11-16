"""Capability purge plans for release 2 L3 (#128 C-8): superadmin-only, previewed, audited.

* `membership.id_programmes` -- every programme hosted by the space, its holder cards
  (photos included), import runs and programme designs. Member cards stay.
* `events.id_cards` -- every event ID card and every event card/ticket design. Event
  registrations stay.
Verify tokens, extras, wallet passes and photo requests cascade from their cards.
"""


def _programmes(space):
    from apps.id_programmes.models import IdProgramme, IdProgrammeCard
    return IdProgramme.objects.filter(makerspace=space), IdProgrammeCard.objects.filter(makerspace=space)


def _programme_delete(space, cursor):
    from apps.card_designs.models import CardDesign
    from .module_purge_collectors_single_model import _counts, _delete
    programmes, cards = _programmes(space)
    designs, design_labels = _delete(CardDesign.objects.filter(makerspace=space, domain="id_programme"))
    card_count, card_labels = _delete(cards)
    count, labels = _delete(programmes)
    return _counts(model_labels=design_labels | card_labels | labels, programme_cards=card_count,
                   id_programmes=count, card_designs=designs)


def _programme_preview(space):
    from apps.card_designs.models import CardDesign
    programmes, cards = _programmes(space)
    return {"id_programmes": programmes.count(), "programme_cards": cards.count(),
            "card_designs": CardDesign.objects.filter(makerspace=space, domain="id_programme").count()}


def _programme_keys(space, add):
    _programmes_list, cards = _programmes(space)
    for key in cards.exclude(photo_object_key="").values_list("photo_object_key", flat=True):
        add(key)


def _event_cards(space):
    from apps.card_designs.models import CardDesign
    from apps.events.models import EventIdCard
    return (EventIdCard.objects.filter(makerspace=space),
            CardDesign.objects.filter(makerspace=space, domain__in=("event_card", "event_ticket")))


def _event_delete(space, cursor):
    from .module_purge_collectors_single_model import _counts, _delete
    cards, designs = _event_cards(space)
    card_count, card_labels = _delete(cards)
    design_count, design_labels = _delete(designs)
    return _counts(model_labels=card_labels | design_labels, event_id_cards=card_count, card_designs=design_count)


def _event_preview(space):
    cards, designs = _event_cards(space)
    return {"event_id_cards": cards.count(), "card_designs": designs.count()}


def _event_keys(space, add):
    cards, _designs = _event_cards(space)
    for key in cards.exclude(photo_object_key="").values_list("photo_object_key", flat=True):
        add(key)


def plans(plan):
    return (
        plan("membership.id_programmes", "ID programmes hosted here, their holder cards and photos, import runs "
             "and programme card designs. Member cards stay.", _programme_delete, _programme_preview, _programme_keys),
        plan("events.id_cards", "Event ID cards, their photos, and event card and ticket designs. Registrations stay.",
             _event_delete, _event_preview, _event_keys),
    )
