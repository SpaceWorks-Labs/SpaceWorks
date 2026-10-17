"""Reconcile modern IDs and legacy slugs without transferring delay/history."""

from rest_framework.exceptions import ValidationError
from .models_website_revisions import EventSessionIdentity, EventSessionAlias


def reconcile(page, rows):
    working = {row.identity_id: row for row in page.sessions.all()}
    by_slug = {row.slug: row for row in working.values()}
    aliases = {row.slug: row.identity_id for row in page.session_aliases.all()}
    identities = set(page.session_identities.values_list("pk", flat=True))
    seen, resolved = set(), []
    for row in rows:
        values = dict(row)
        supplied = values.pop("session_id", None)
        slug = values["slug"]
        if supplied is not None:
            if supplied not in identities:
                raise ValidationError({"session_id": "Session identity must belong to this page."})
            identity = supplied
            if slug in aliases and aliases[slug] != identity:
                raise ValidationError({"slug": "This slug is permanently reserved for another session."})
        elif slug in by_slug:
            identity = by_slug[slug].identity_id
        elif slug in aliases:
            raise ValidationError({"slug": "This retired session slug is permanently reserved."})
        else:
            identity = EventSessionIdentity.objects.create(page=page).pk
        if identity in seen:
            raise ValidationError({"session_id": "A session identity can appear only once."})
        seen.add(identity)
        if slug not in aliases:
            EventSessionAlias.objects.create(page=page, identity_id=identity, slug=slug)
            aliases[slug] = identity
        values["identity_id"] = identity
        values["delay_minutes"] = working[identity].delay_minutes if identity in working else 0
        resolved.append(values)
    return resolved


def delay_targets(page):
    working = {str(row.identity_id): row for row in page.sessions.all()}
    public = {}
    if page.released and page.published_revision_id:
        from .website_revision_projection import snapshot_sessions
        public = {row["session_id"]: row for row in snapshot_sessions(page.published_revision, public=True)}
    return [{"session_id": identity, "working_slug": working[identity].slug if identity in working else None,
             "public_slug": public[identity]["slug"] if identity in public else None,
             "working_present": identity in working, "public_present": identity in public,
             "working_delay_minutes": working[identity].delay_minutes if identity in working else None,
             "public_delay_minutes": public[identity]["delay_minutes"] if identity in public else None}
            for identity in sorted(set(working) | set(public))]
