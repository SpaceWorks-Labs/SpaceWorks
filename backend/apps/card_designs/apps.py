from django.apps import AppConfig


class CardDesignsConfig(AppConfig):
    """The shared card engine (release 2 L3): core, not separable, no module key."""
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.card_designs"
    verbose_name = "Card designs"

    def ready(self):
        from .holders_member import register as register_member_holder
        register_member_holder()
        from .registration import register_runtime
        register_runtime()
