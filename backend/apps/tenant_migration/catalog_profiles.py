"""Reviewed authored-content/namespace portability for the public profile contract."""

PROFILE_FIELDS = ("public_visible public_consented_at show_activity_graph show_events show_speaking "
                  "show_projects show_machine_activity show_bookings show_loans domains skills links")
PROJECT_FIELDS = "subtitle tags public_visible"
EXPORTED_FIELDS = {
    "makerspaces.PublicHandle": "id user profile handle claimed_at changed_at",
    "makerspaces.ProfileTimelineEntry": "id profile kind title organization location start end description order",
}
FIELD_NAMES = {label: frozenset(fields.split()) for label, fields in EXPORTED_FIELDS.items()}
FIELD_NAMES["makerspaces.PublicHandleRedirect"] = frozenset(
    "id profile handle released_at expires_at".split())
OMITTED_MODELS = {"makerspaces.PublicHandleRedirect": "Retired namespace reservations are deployment-local."}


def authority_entries(authority, D):
    entries = []
    for field in PROFILE_FIELDS.split():
        reset = field.startswith("show_") or field in ("public_visible", "public_consented_at")
        entries.append((("makerspaces.MemberProfile", field), authority(
            D.RESET if reset else (D.PRESERVE, D.DROP),
            "Reset public disclosure; preserve authored content only for full users.")))
    for field in PROJECT_FIELDS.split():
        entries.append((("makerspaces.MemberProject", field), authority(
            D.RESET if field == "public_visible" else (D.PRESERVE, D.DROP),
            "Imported authored projects require target publication.")))
    for label, fields in EXPORTED_FIELDS.items():
        for field in fields.split():
            entries.append(((label, field), authority((D.PRESERVE, D.DROP),
                "Full-user authored content travels; handle conflicts drop without overwriting target claims.")))
    return entries


def projections(TargetField):
    resets = {("makerspaces.MemberProfile", field): TargetField(False, reason=
              "Public disclosure requires fresh target-side member consent.")
              for field in PROFILE_FIELDS.split() if field.startswith("show_") or field == "public_visible"}
    resets[("makerspaces.MemberProfile", "public_consented_at")] = TargetField(
        None, reason="Source consent never authorizes publication on the target.")
    resets[("makerspaces.MemberProject", "public_visible")] = TargetField(
        False, reason="Imported projects require fresh target publication.")
    return resets


def prepare_import_handle(row, reservations=None):
    """Called with remapped IDs in the importer transaction. Collision drops the claim.

    Never rename/overwrite a target claim, and never revive a retired reservation.
    Import uses the very same account + namespace locks as interactive claims.
    """
    from django.contrib.auth import get_user_model
    from apps.makerspaces.models_profiles import PublicHandle, MemberProfile
    from apps.makerspaces.public_profile_handles import normalize_handle, lock_names, name_available
    from rest_framework.exceptions import ValidationError
    try:
        handle = normalize_handle(row["handle"])
    except ValidationError:
        return False
    reservations = reservations if reservations is not None else {}
    handles = reservations.setdefault(("makerspaces.PublicHandle", "handle"), set())
    users = reservations.setdefault(("makerspaces.PublicHandle", "user"), set())
    if handle in handles or row["user_id"] in users:
        return False
    get_user_model().objects.select_for_update(no_key=True).get(pk=row["user_id"])
    lock_names(handle)
    if PublicHandle.objects.filter(user_id=row["user_id"]).exists() or not name_available(handle):
        return False
    if not MemberProfile.objects.filter(pk=row["profile_id"], membership__user_id=row["user_id"]).exists():
        return False
    row["handle"] = handle
    handles.add(handle)
    users.add(row["user_id"])
    return True
