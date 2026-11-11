"""Capability purge plan for parity O-B4: `membership.card_numbering` (superadmin-only, previewed, audited).

Deletes the numbering schemes and their counters. Cards keep the number already printed on them
(`MemberCard.number_text` is frozen at issue); only future numbering returns to the membership-number display.
"""


def _delete(space, cursor):
    from .module_purge_collectors_single_model import _counts, _delete as delete_rows
    from apps.card_designs.models_numbering import CardNumberCounter, CardNumberScheme
    schemes, labels = delete_rows(CardNumberScheme.objects.filter(makerspace=space))
    counters, counter_labels = delete_rows(CardNumberCounter.objects.filter(makerspace=space))
    return _counts(model_labels=labels | counter_labels, card_number_schemes=schemes, card_number_counters=counters)


def _preview(space):
    from apps.card_designs.models_numbering import CardNumberCounter, CardNumberScheme
    return {"card_number_schemes": CardNumberScheme.objects.filter(makerspace=space).count(),
            "card_number_counters": CardNumberCounter.objects.filter(makerspace=space).count()}


def _staff_delete(space, cursor):
    from apps.card_designs.models import CardDesign, CardNumberCounter, StaffCard, StaffCardNumbering
    from .module_purge_collectors_single_model import _counts, _delete as delete_rows
    cards, labels = delete_rows(StaffCard.objects.filter(makerspace=space))
    numbering, numbering_labels = delete_rows(StaffCardNumbering.objects.filter(makerspace=space))
    counters, counter_labels = delete_rows(CardNumberCounter.objects.filter(makerspace=space, scheme_key="staff"))
    designs, design_labels = delete_rows(CardDesign.objects.filter(makerspace=space, domain="staff_cards"))
    return _counts(model_labels=labels | numbering_labels | counter_labels | design_labels, staff_cards=cards,
                   staff_card_numbering=numbering, staff_card_counters=counters, staff_card_designs=designs)


def _staff_preview(space):
    from apps.card_designs.models import CardDesign, StaffCard
    return {"staff_cards": StaffCard.objects.filter(makerspace=space).count(),
            "staff_card_designs": CardDesign.objects.filter(makerspace=space, domain="staff_cards").count()}


def plans(plan):
    return (
        plan("membership.staff_cards", "Staff ID cards, their public check links, number scheme and design. "
             "Staff roles stay.", _staff_delete, _staff_preview),
        plan("membership.card_numbering", "Card numbering schemes and counters. Numbers already printed on "
             "cards stay.", _delete, _preview),
    )
