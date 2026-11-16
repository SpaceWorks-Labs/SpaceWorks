from django.apps import AppConfig


class ShopConfig(AppConfig):
    """The per-makerspace shop (release 2 L22, #128 C-7, #129, #135-#137): separable, switched
    by the `shop` module key (an owner exception to #97)."""
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.shop"
    verbose_name = "Shop"

    def ready(self):
        from apps.encryption.registry import register_retained_pii
        from apps.separability.tombstones import app_is_tombstoned, register_separable_app

        register_retained_pii("shop.")
        register_separable_app("shop")
        if not app_is_tombstoned("shop"):
            from .notices import register
            register()
