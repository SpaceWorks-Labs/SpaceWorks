from django.apps import AppConfig


class PaymentsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.payments"

    def ready(self):
        # A ModelSerializer over a money column renders it like a hundredth when exact ("25.00"),
        # not as the stored thousandth ("25.000"); the explicit MoneyField sites already did.
        from rest_framework import serializers as drf_serializers
        from .money_fields import MoneyField
        from .money_model import MoneyDecimalField
        drf_serializers.ModelSerializer.serializer_field_mapping[MoneyDecimalField] = MoneyField
        from apps.encryption.registry import register_retained_pii
        register_retained_pii("payments.")
        from .notifications_p2 import register
        register()
        from .notifications_refund_cases import register as register_refund_cases
        register_refund_cases()
        from .notifications_l5 import register as register_l5
        register_l5()
        from .event_payout_bridge import install
        install()
        from .donations.notices import register as register_donations  # lane L18
        register_donations()

    # No `register_separable_app`: the payment ledger is permanently core. Its surfaces
    # are the record of money owed and taken, and a deployment that cannot read or settle
    # them has lost data it is still holding. The removable half is `apps.payments_rail`.
