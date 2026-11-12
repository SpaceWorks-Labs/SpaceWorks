"""One-time notice that a profile is now open by default (decision 303d).

Sent ONCE to each person whose legacy profile was merged without an explicit hide (the merge sets
`AccountProfile.open_notice_pending`). The notice is a member inbox/email intent through the
notification catalogue (translated in the recipient's language, preferences respected), minted in
the person's home space because every envelope is space-scoped; it links to the profile settings.
This sweep also backfills a profile row (and the default handle) for member accounts that have
none yet. It rides the hourly membership sweep, one tenant at a time.
"""
from django.utils.translation import gettext

from apps.hardware_requests.notifications_p2 import fanout, revision, safe_adapter
from apps.integrations.notification_links import local_link
from apps.integrations.notification_sources import NotificationSource, register_source

KIND = "members.profile_open"
EVENT = "profile_opened"
BATCH = 200


def _version(profile):
    return revision(profile.pk, "open-notice-v1")


@safe_adapter
def notify_opened(profile, space):
    reconfirm = profile.public_reconfirm_pending

    def own():  # built in the recipient's language by emit()
        text = gettext("Member profiles are now open by default for signed-in users. You can hide your whole "
                       "profile or any section in your profile settings.")
        if reconfirm:
            # Decision 335c: the merge switched the open web off; ask once to confirm it again.
            text += " " + gettext("Your profiles from different spaces were combined into one, so publishing it "
                                  "on the open web is off until you confirm it again in your profile settings.")
        return {"subject": gettext("Your profile is now visible to other members"), "text": text,
                "link": local_link(space, "member")}
    return fanout(space=space, feature="members", stream="membership", event=EVENT, kind=KIND,
                  source=profile.pk, version=_version(profile), subject=profile, owner=profile.user,
                  own=own, staff=None, context={})


def eligible(envelope):
    from .models_account_profile import AccountProfile

    profile = AccountProfile.objects.filter(pk=envelope.source_id).first()
    return bool(profile and profile.is_visible and envelope.audience == "requester"
                and profile.user_id == envelope.recipient_id and _version(profile) == envelope.revision)


def register():
    register_source(KIND, NotificationSource(eligible))


def send_open_notices():
    """Backfill missing profiles, then deliver pending notices. Returns the number sent."""
    from apps.accounts.models import User
    from apps.tenant_migration.gate_runtime import fanout_tenant_write

    from .account_profile import account_profile_for
    from .models_account_profile import AccountProfile
    from .profile_images import home_space

    for user in User.objects.filter(account_kind="member", is_active=True, account_profile__isnull=True,
                                    merged_into__isnull=True, retired_at__isnull=True)[:BATCH]:
        account_profile_for(user)
    counts, sent = {"skipped": 0}, 0
    pending = AccountProfile.objects.filter(open_notice_pending=True, is_visible=True).select_related("user")
    for profile in pending.order_by("pk")[:BATCH]:
        space = home_space(profile.user)
        if space is None:
            continue
        with fanout_tenant_write(space.pk, operation="profile_open_notice", counts=counts) as go:
            if not go:
                continue
            if notify_opened(profile, space) is not None:
                sent += 1
            AccountProfile.objects.filter(pk=profile.pk).update(open_notice_pending=False)
    return sent
