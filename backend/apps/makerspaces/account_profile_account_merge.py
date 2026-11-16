"""Account merge (unified accounts): fold the source's profile into the survivor's (decision 305).

The merge registry can only MOVE a row or leave it on the shell; two profiles for one person need
their CONTENT combined. Survivor scalars win, empty ones are filled from the source, lists are the
deduplicated union, and timeline entries, projects and self-reported achievements are copied across
(capped like interactive writes). When the survivor has no profile the registry simply moves the
source's row. The source row is then deleted; an avatar the survivor did not adopt is left to the
normal public-image cleanup (its key is no longer referenced).
"""

from .models_account_profile import (
    ACTIVITY_TOGGLES, SECTION_TOGGLES, AccountProfile, AccountProject, AccountTimelineEntry, ProfileAchievement,
)

SCALARS = ("headline", "status", "status_note", "institution", "bio", "avatar_key")


def _extend(target, source, key):
    seen = {key(row) for row in target}
    return target + [row for row in source if key(row) not in seen]


def merge_profiles(source_id, survivor_id):
    """Returns True when two profiles were combined, False when nothing needed doing."""
    source = AccountProfile.objects.select_for_update().filter(user_id=source_id).first()
    survivor = AccountProfile.objects.select_for_update().filter(user_id=survivor_id).first()
    if source is None or survivor is None:
        return False
    for name in SCALARS:
        if not getattr(survivor, name) and getattr(source, name):
            setattr(survivor, name, getattr(source, name))
    if source.avatar_key == survivor.avatar_key:
        source.avatar_key = ""
    lower = lambda row: str(row).strip().lower()  # noqa: E731
    survivor.domains = _extend(list(survivor.domains), [v for v in source.domains if isinstance(v, str)], lower)
    survivor.interests = _extend(list(survivor.interests), [v for v in source.interests if isinstance(v, str)], lower)
    survivor.languages = _extend(list(survivor.languages), [v for v in source.languages if isinstance(v, str)], lower)
    survivor.skills = _extend(list(survivor.skills), [r for r in source.skills if isinstance(r, dict)],
                              lambda r: str(r.get("name", "")).strip().lower())
    survivor.links = _extend(list(survivor.links), [r for r in source.links if isinstance(r, dict)],
                             lambda r: str(r.get("url", "")).strip().lower())
    survivor.education = _extend(list(survivor.education), [r for r in source.education if isinstance(r, dict)], str)
    # SECURITY-REVIEW hardening 13: the source's content now sits on the survivor, so every switch takes
    # the MORE restrictive of the two -- a section either account hid stays hidden, and the open web
    # stays on only when both accounts had consented.
    for name in ("is_visible", *SECTION_TOGGLES, *ACTIVITY_TOGGLES):
        setattr(survivor, name, getattr(survivor, name) and getattr(source, name))
    both_public = source.public_visible and source.public_consented_at is not None
    survivor.public_visible = survivor.public_visible and survivor.public_consented_at is not None and both_public
    if not survivor.public_visible:
        survivor.public_consented_at = None
    survivor.save()
    have = {(e.kind, e.title.lower(), e.organization.lower(), e.start) for e in survivor.timeline.all()}
    room = max(0, 100 - len(have))
    for entry in list(source.timeline.all())[:room]:
        if (entry.kind, entry.title.lower(), entry.organization.lower(), entry.start) not in have:
            AccountTimelineEntry.objects.create(
                profile=survivor, kind=entry.kind, title=entry.title, organization=entry.organization,
                location=entry.location, start=entry.start, end=entry.end, description=entry.description,
                order=entry.order)
    held = {(p.title.lower(), p.subtitle.lower()) for p in survivor.projects.all()}
    imported = set(survivor.projects.exclude(source_submission_id=None).values_list("source_submission_id", flat=True))
    position = survivor.projects.count()
    for project in source.projects.all():
        if position >= 20 or (project.title.lower(), project.subtitle.lower()) in held \
                or (project.source_submission_id in imported and project.source_submission_id is not None):
            continue
        AccountProject.objects.create(
            profile=survivor, title=project.title, subtitle=project.subtitle, tags=project.tags,
            public_visible=project.public_visible, description=project.description,
            image_key=project.image_key if project.image_key else "", links=project.links, position=position,
            source_submission_id=project.source_submission_id)
        AccountProject.objects.filter(pk=project.pk).update(image_key="")
        position += 1
    count = survivor.achievements.count()
    for row in source.achievements.all()[: max(0, 30 - count)]:
        ProfileAchievement.objects.create(
            profile=survivor, title=row.title, issuer=row.issuer, achieved_on=row.achieved_on,
            url=row.url, description=row.description, order=row.order)
    source.delete()
    return True
