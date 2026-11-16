"""The read-only price text a ticket design may merge in (E-B2 D17).

It lives outside the ``id_cards*`` modules on purpose: ID cards never charge (C-20), and the static guard in
``tests/money_modes/test_id_cards_never_charge.py`` keeps every card module free of payments imports. This only
formats an amount the ticket type already holds; it records and collects nothing.
"""
from django.utils.translation import gettext


def price_label(event, ticket_type):
    if ticket_type is None:
        return ""
    if not ticket_type.amount:
        return gettext("Free")
    from apps.payments.donations.services import space_currency
    from apps.payments.money import money_text
    return f"{space_currency(event.makerspace)} {money_text(ticket_type.amount)}".strip()
