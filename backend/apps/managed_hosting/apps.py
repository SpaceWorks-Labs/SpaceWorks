from django.apps import AppConfig


class ManagedHostingConfig(AppConfig):
    """The managed-hosting limiter (owner decision #187A), OFF by default.

    With ``MANAGED_PLANS_ENABLED`` off (the default) or on a self-host, nothing here is
    visible or enforced: every route 404s, every hook returns "not set", and the fair-use
    limits in ``makerspaces/limits*.py`` behave exactly as before.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.managed_hosting"
    verbose_name = "Managed hosting"

    def ready(self):
        # #234: every DRF throttle reads its rate through the superadmin override table.
        from .throttle_rates import install

        install()
