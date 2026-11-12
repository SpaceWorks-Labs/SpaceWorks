"""Merge each person's per-membership profiles into one `AccountProfile` (decision 304d).

Pure data code over a ``models`` namespace (``SimpleNamespace`` of the model classes) so migration
0153 can call it with *historical* models and the tests with the real ones. No audit, no cache, no
storage I/O: a migration must be repeatable and must not reach outside the database.

Rules:

* The most recently updated legacy profile supplies the scalar content; empty scalars are filled
  from the next most recent. Skills, links, domains, interests, languages, education, timeline
  entries and projects are the **deduplicated union** of all of them.
* Avatar and project image keys are **reused, not copied**: the legacy row keeps pointing at the
  same object and `public_image_storage.public_image_key_in_use` / the purge collectors know the
  account rows are a second holder (see `profile_images`).
* Decision 303d: a profile counts as explicitly hidden only when a `member.profile_updated` audit
  row shows a REAL visibility change (``visibility_changed`` true) whose latest value is hidden.
  Everyone else gets the new open default and a one-time notice (`open_notice_pending`).
* Content sources (SECURITY-REVIEW H2): when ANY legacy row was visible, content is merged only
  from the visible rows -- a profile the member kept hidden in one space never pours its content
  into sections that are now shown. Only when no row was ever visible (the 303d opening) or the
  member explicitly hid the profile (nothing is shown at all) do all rows contribute.
* Legacy publication consents (attended events, activity graph, projects, certifications, the
  activity families) carry over as ``any(...)`` across the contributing rows and nothing else: an
  explicit legacy "no" stays "no", and nobody gains a disclosure from the merge.
* Open web (decision 335c): ``public_visible`` only when EVERY contributing row had the open-web
  consent; when some row had it but the merged profile does not, ``public_reconfirm_pending`` asks
  the member to confirm again (one-time notice + profile banner).
* Idempotent: a user who already has an `AccountProfile` is skipped; legacy rows are never edited.
"""

import json

SCALARS = ("headline", "status", "status_note", "institution", "bio")


def _union(rows, key):
    seen, out = set(), []
    for row in rows:
        marker = key(row)
        if marker in seen:
            continue
        seen.add(marker)
        out.append(row)
    return out


def _strings(profiles, field):
    values = [v for p in profiles for v in (getattr(p, field) or []) if isinstance(v, str) and v.strip()]
    return [v for v in _union(values, lambda v: v.strip().lower())]


def _skills(profiles):
    best = {}
    order = []
    for profile in profiles:
        for row in profile.skills or []:
            if not isinstance(row, dict) or not row.get("name"):
                continue
            key = str(row["name"]).strip().lower()
            if key not in best:
                order.append(key)
                best[key] = dict(row)
            else:
                best[key]["level"] = max(int(best[key].get("level") or 1), int(row.get("level") or 1))
    return [best[key] for key in order]


def _dicts(profiles, field, key):
    rows = [r for p in profiles for r in (getattr(p, field) or []) if isinstance(r, dict)]
    return _union(rows, key)


def explicitly_hidden(models, user_id):
    """True only when the member's latest recorded visibility change set the profile hidden."""
    row = models.AuditLog.objects.filter(
        actor_id=user_id, action="member.profile_updated", meta__visibility_changed=True,
    ).order_by("-created_at", "-id").values_list("meta", flat=True).first()
    return bool(row) and row.get("is_visible") is False


def _merge_content(models, account, profiles):
    timeline, projects = [], []
    for profile in profiles:
        timeline += list(models.ProfileTimelineEntry.objects.filter(profile=profile))
        projects += list(models.MemberProject.objects.filter(profile=profile))
    entries = _union(timeline, lambda e: (e.kind, e.title.strip().lower(), e.organization.strip().lower(), e.start))
    for position, entry in enumerate(entries):
        models.AccountTimelineEntry.objects.create(
            profile=account, kind=entry.kind, title=entry.title, organization=entry.organization,
            location=entry.location, start=entry.start, end=entry.end,
            description=entry.description, order=position)
    kept = _union(projects, lambda p: (p.title.strip().lower(), p.subtitle.strip().lower()))
    for position, project in enumerate(kept):
        models.AccountProject.objects.create(
            profile=account, title=project.title, subtitle=project.subtitle, tags=project.tags,
            public_visible=project.public_visible, description=project.description,
            image_key=project.image_key, links=project.links, position=position)


def _consented(profile):
    return bool(profile.public_visible and profile.public_consented_at)


def _sources(profiles, hidden):
    """The rows whose content and consents feed the merged profile (H2)."""
    visible = [p for p in profiles if p.is_visible]
    return visible if visible and not hidden else profiles


def merge_user(models, user_id):
    """Create the account profile for one user from their legacy rows; None when not needed."""
    if models.AccountProfile.objects.filter(user_id=user_id).exists():
        return None
    profiles = list(models.MemberProfile.objects.filter(membership__user_id=user_id).order_by("-updated_at", "-id"))
    if not profiles:
        return None
    hidden = explicitly_hidden(models, user_id)
    sources = _sources(profiles, hidden)
    # Legacy per-space rows never had `status`/`status_note`; those start blank on the account.
    values = {name: next((getattr(p, name) for p in sources if getattr(p, name, "")), "") for name in SCALARS}
    avatar = next((p.avatar_key for p in sources if p.avatar_key), "")
    public = all(_consented(p) for p in sources)
    stamps = [p.public_consented_at for p in sources if _consented(p)]
    source = next((p for p in sources if p.github_username), None)
    github = ({"github_username": source.github_username, "github_contributions": source.github_contributions,
               "github_synced_at": source.github_synced_at} if source else {})
    account = models.AccountProfile.objects.create(
        user_id=user_id, is_visible=not hidden, avatar_key=avatar,
        public_visible=public, public_consented_at=max(stamps) if public else None,
        public_reconfirm_pending=not public and any(_consented(p) for p in profiles),
        domains=_strings(sources, "domains"), interests=_strings(sources, "interests"),
        languages=_strings(sources, "languages"), skills=_skills(sources),
        links=_dicts(sources, "links", lambda r: str(r.get("url", "")).strip().lower()),
        education=_dicts(sources, "education", lambda r: json.dumps(r, sort_keys=True)),
        merged_from_legacy=True, open_notice_pending=not hidden,
        # Every legacy consent carries over only as True from a contributing row: a person who allowed
        # one before still allows it; an explicit (or default) "no" stays "no" (H2).
        show_events=any(p.show_attended_events for p in sources),
        show_activity_graph=any(p.show_activity_graph for p in sources),
        show_projects=any(p.show_projects for p in sources),
        show_certifications=any(p.show_certifications for p in sources),
        show_speaking=any(p.show_speaking for p in sources),
        show_machine_activity=any(p.show_machine_activity for p in sources),
        show_bookings=any(p.show_bookings for p in sources),
        show_loans=any(p.show_loans for p in sources),
        **github, **values)
    _merge_content(models, account, sources)
    return account


def merge_all(models):
    user_ids = (models.MemberProfile.objects.order_by().values_list("membership__user_id", flat=True).distinct())
    return [account for uid in list(user_ids) if (account := merge_user(models, uid)) is not None]
