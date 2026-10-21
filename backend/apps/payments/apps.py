from django.apps import AppConfig


class PaymentsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.payments"

    def ready(self):
        from .notifications_p2 import register
        register()
        from .notifications_refund_cases import register as register_refund_cases
        register_refund_cases()

    # No `register_separable_app`: the payment ledger is permanently core. Its surfaces
    # are the record of money owed and taken, and a deployment that cannot read or settle
    # them has lost data it is still holding. The removable half is `apps.payments_rail`.
