"""Decision 223 (f): react to a new damage/loss accountability row, once, after the return commits."""
from django.db.models.signals import post_save
from django.dispatch import receiver

from .guest_liability import schedule_accountability_hook
from .return_models import RequesterAccountability


@receiver(post_save, sender=RequesterAccountability, dispatch_uid="guest_pass_accountability_hook")
def accountability_created(sender, instance, created, **kwargs):
    if created:
        schedule_accountability_hook(instance.pk)
