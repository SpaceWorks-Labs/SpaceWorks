"""Fetch the pinned photo clean-up model (Q-I3) to CARD_PHOTO_MODEL_PATH; checksum-verified."""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Download the pinned background clean-up model used for card photos (runs on this server only)."

    def handle(self, *args, **options):
        from apps.card_designs.segmentation import fetch_model
        self.stdout.write(f"Model ready at {fetch_model()}")
