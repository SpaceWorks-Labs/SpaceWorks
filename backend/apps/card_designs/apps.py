from django.apps import AppConfig


class CardDesignsConfig(AppConfig):
    """The shared card engine (release 2 L3): core, not separable, no module key."""
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.card_designs"
    verbose_name = "Card designs"

    def ready(self):
        from .holders_member import register as register_member_holder
        register_member_holder()
        from .holders_staff import register as register_staff_holder
        register_staff_holder()
        from .registration import register_runtime
        register_runtime()
        from django.db.models.signals import post_delete
        from .cutouts import release_deleted
        from .models_cutout import CardPhotoCutout
        post_delete.connect(release_deleted, sender=CardPhotoCutout, dispatch_uid="card_photo_cutout_release")
        from .models_cutout import CardPhotoBatchItem
        from .photo_batch import release_item_file
        post_delete.connect(release_item_file, sender=CardPhotoBatchItem, dispatch_uid="card_photo_batch_item_release")
