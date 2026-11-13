"""Recompute programme email digests after a tenant move (they are keyed per deployment)."""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Recompute ID-programme email digests from the stored (encrypted) emails."

    def handle(self, *args, **options):
        from apps.id_programmes.cards import email_digest
        from apps.id_programmes.models import IdProgrammeCard
        changed = 0
        for card in IdProgrammeCard.objects.exclude(email="").iterator():
            digest = email_digest(card.email)
            if digest != card.email_digest:
                IdProgrammeCard.objects.filter(pk=card.pk).update(email_digest=digest)
                changed += 1
        self.stdout.write(f"{changed} digests rebuilt")
