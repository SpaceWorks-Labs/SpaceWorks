"""Django admin barrel for the card engine: importing the submodules fires their `@admin.register`."""
from apps.card_designs import admin_staff_cards  # noqa: F401
