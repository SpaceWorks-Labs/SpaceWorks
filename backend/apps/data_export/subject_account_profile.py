"""The member's own global profile in their subject-access export (SECURITY-REVIEW M17, decision 336f).

The four account-profile models are account-level data, so they are OMITTED from every tenant
dataset (`classification_account_profile`) and no per-space dataset can carry them. A person's
right of access still covers them: this adds them to the person's own subject export as a separate
`account_profile/` section, built from the requester alone -- never another person's row, never an
object key (photo bytes are outside every subject export, see the manifest's omissions).
"""

from django.forms.models import model_to_dict

PROFILE_EXCLUDED = ("id", "user", "avatar_key", "merged_from_legacy", "open_notice_pending")
CHILD_EXCLUDED = ("id", "profile", "image_key")


def _plain(instance, excluded):
    data = model_to_dict(instance, exclude=excluded)
    # `editable=False` fields are skipped by model_to_dict; the consent stamp is the person's own record.
    for name in ("public_consented_at", "public_reconfirm_pending", "created_at", "updated_at"):
        if hasattr(instance, name) and name not in excluded:
            data[name] = getattr(instance, name)
    return data


def account_profile_records(user):
    """`{section: [rows]}` for the requester's own global profile; every section empty when there is none."""
    from apps.makerspaces.models_account_profile import AccountProfile
    from apps.makerspaces.models_profiles import PublicHandle

    profile = AccountProfile.objects.filter(user_id=user.pk).first()
    if profile is None:
        return {"profile": [], "projects": [], "timeline": [], "achievements": []}
    row = _plain(profile, PROFILE_EXCLUDED)
    row["handle"] = PublicHandle.objects.filter(user_id=user.pk).values_list("handle", flat=True).first()
    return {
        "profile": [row],
        "projects": [_plain(p, CHILD_EXCLUDED) for p in profile.projects.order_by("position", "pk")],
        "timeline": [_plain(e, CHILD_EXCLUDED) for e in profile.timeline.order_by("order", "pk")],
        "achievements": [_plain(a, CHILD_EXCLUDED) for a in profile.achievements.order_by("order", "pk")],
    }
