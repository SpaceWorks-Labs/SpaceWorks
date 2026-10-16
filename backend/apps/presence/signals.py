"""Invalidate current display generations in the same transaction as a change."""
from django.db.models.signals import post_delete, post_save

from .cache import bump_version
from .models import PresencePreference, PresenceSession, PresenceSettings


def changed(sender, instance, **kwargs):
    if kwargs.get("raw"):
        return
    label = sender._meta.label
    if label in {"presence.PresenceSession", "presence.PresencePreference", "presence.PresenceSettings"}:
        ids = [instance.makerspace_id]
    elif label == "makerspaces.MemberProject":
        ids = PresenceSession.objects.filter(project_id=instance.pk, ended_at=None).values_list("makerspace_id", flat=True)
    elif label == "makerspaces.MemberProfile":
        ids = PresenceSession.objects.filter(project__profile=instance, ended_at=None).values_list("makerspace_id", flat=True)
    elif label == "events.Event":
        ids = PresenceSession.objects.filter(event_registration__event=instance, ended_at=None).values_list("makerspace_id", flat=True)
    elif label == "events.EventRegistration":
        ids = PresenceSession.objects.filter(event_registration=instance, ended_at=None).values_list("makerspace_id", flat=True)
    elif label == "makerspaces.MakerspaceMembership":
        ids = [instance.makerspace_id]
    elif label == "accounts.User":
        ids = PresenceSession.objects.filter(account=instance, ended_at=None).values_list("makerspace_id", flat=True)
    else:
        return
    for makerspace_id in set(ids):
        bump_version(makerspace_id)


def register():
    from apps.events.models import Event, EventRegistration
    from apps.makerspaces.models import MakerspaceMembership, MemberProject, MemberProfile
    from django.contrib.auth import get_user_model
    for model in (PresenceSession, PresencePreference, PresenceSettings, MemberProject, MemberProfile,
                  Event, EventRegistration, MakerspaceMembership, get_user_model()):
        for signal in (post_save, post_delete):
            signal.connect(changed, sender=model, dispatch_uid=f"presence.{signal}.{model._meta.label}", weak=False)
