from django.apps import AppConfig


class IdProgrammesConfig(AppConfig):
    """Organisation ID programmes (release 2 L3): separable, switched by the
    `membership.id_programmes` capability, no module key of its own (#128 C-12)."""
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.id_programmes"
    verbose_name = "ID programmes"

    def ready(self):
        from apps.encryption.registry import register_retained_pii
        from apps.separability.tombstones import app_is_tombstoned, register_separable_app

        register_retained_pii("id_programmes.")
        register_separable_app("id_programmes")
        if not app_is_tombstoned("id_programmes"):
            from .holders import register
            register()
