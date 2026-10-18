"""Paired consent clearing before a selected profile or membership disappears."""
from django.db import transaction
from django.db.models.signals import pre_delete
from django.utils import timezone

from apps.audit.services import record


def clear_selections(rows, *, actor=None):
    from .models import EventMemberPresentation
    with transaction.atomic():
        selected = list(rows.select_for_update().order_by("pk"))
        for row in selected:
            # One UPDATE is essential: two SET_NULL updates violate the shape CHECK.
            EventMemberPresentation.objects.filter(pk=row.pk).update(
                selected_profile=None, selected_membership=None, source_revision="",
                print_photo_consent=False, public_card_consent=False, public_card_scopes=[],
                consented_at=None, revoked_at=timezone.now(), version=row.version + 1,
                consent_revision=row.consent_revision + 1)
            record(actor, "event.presentation_updated", makerspace=row.event.makerspace, target=row,
                   meta={"version": row.version + 1, "consent_revision": row.consent_revision + 1,
                         "print_photo_consent": False, "public_card_consent": False, "scopes": []})
        return len(selected)


def source_deleting(sender, instance, using, **kwargs):
    from .models import EventMemberPresentation
    if using != "default":
        raise RuntimeError("Presentation lifecycle requires the application database.")
    lookup = {"selected_profile_id" if sender._meta.model_name == "memberprofile"
              else "selected_membership_id": instance.pk}
    clear_selections(EventMemberPresentation.objects.filter(**lookup))


def register_source_lifecycle():
    from apps.separability.tombstones import app_is_tombstoned
    if app_is_tombstoned("events"):
        return
    # String senders keep this separable and query-free during model discovery.
    pre_delete.connect(source_deleting, sender="makerspaces.MemberProfile",
                       dispatch_uid="events.presentation.profile_delete", weak=False)
    pre_delete.connect(source_deleting, sender="makerspaces.MakerspaceMembership",
                       dispatch_uid="events.presentation.membership_delete", weak=False)
    from apps.accounts.erasure_hooks import register
    from .erasure import EventSubjectErasure
    register("events", EventSubjectErasure)
