"""Tell a named guardian account that their signed consent is wanted (decision 223 (k), minors).

Sent when staff record a minor whose guardian has an account and no current consent exists, and again ONCE per
newly published terms version to every guardian whose consent is on an older version (`notify_terms_changed`).
Owner leg only,
to the guardian: it never carries the minor's name, age or any detail (the guardian reads those after signing
in), and the minor is never notified. Staff made the record and the audit row keeps it.
"""
from django.utils.translation import gettext

from apps.accounts import rbac
from apps.hardware_requests.notifications_p2 import fanout, revision, safe_adapter
from apps.integrations.notification_links import local_link
from apps.integrations.notification_sources import NotificationSource, register_source

KIND = "members.guardian_consent"
EVENT = "guardian_consent_requested"
FEATURE = "membership.minors"


def _version(profile):
    """Includes the active terms version, so one publish is one fresh ask and a repeat is a no-op."""
    from .minors import active_terms
    terms = active_terms(profile.makerspace)
    return revision(profile.pk, profile.updated_at, profile.guardian_user_id, terms.version if terms else "")


@safe_adapter
def notify_requested(profile):
    from .minors import current_consent
    if profile.guardian_user_id is None or profile.cleared_at is not None or current_consent(profile) is not None:
        return None
    space = profile.makerspace
    own = lambda: {  # noqa: E731 - built in the guardian's language by emit()
        "subject": gettext("%(space)s needs your guardian consent") % {"space": space.name},
        "text": gettext("%(space)s has named you as a guardian. Sign in and review the guardian consent on "
                        "your Home page so they can confirm it.") % {"space": space.name},
        "link": local_link(space, "member")}
    return fanout(space=space, feature="members", stream="membership", event=EVENT, kind=KIND,
                  source=profile.pk, version=_version(profile), subject=profile, owner=profile.guardian_user,
                  own=own, staff=None, context={"minor_profile_id": profile.pk})


def notify_terms_changed(makerspace):
    """After new guardian terms are published: ask every named guardian account without a current consent.

    Gated on `membership.minors`; the dedup revision carries the terms version, so each version asks once.
    """
    from apps.makerspaces.platform import feature_enabled

    from .models import MinorProfile
    if not feature_enabled(makerspace, FEATURE):
        return 0
    sent = 0
    profiles = MinorProfile.objects.filter(makerspace=makerspace, cleared_at__isnull=True,
                                           guardian_user__isnull=False).select_related("guardian_user", "makerspace")
    for profile in profiles.order_by("pk").iterator(chunk_size=200):
        if notify_requested(profile) is not None:
            sent += 1
    return sent


def eligible(envelope):
    from apps.makerspaces.platform import feature_enabled
    from apps.makerspaces.servability import is_servable

    from .minors import current_consent
    from .models import MinorProfile
    profile = rbac.scope_notification_policy(MinorProfile.objects.all(),
        makerspace_id=envelope.makerspace_id).select_related("makerspace").filter(pk=envelope.source_id).first()
    return bool(profile and envelope.audience == "requester" and profile.guardian_user_id == envelope.recipient_id
                and profile.cleared_at is None and _version(profile) == envelope.revision
                and current_consent(profile) is None and is_servable(profile.makerspace)
                and feature_enabled(profile.makerspace, FEATURE))


def register():
    register_source(KIND, NotificationSource(eligible))
