"""Exact working/draft agreement after remapping, before opening the target."""

import json
from copy import deepcopy
from datetime import datetime
from .insertion_errors import ImportVerificationError


def verify_event_draft(page):
    from apps.events.website_revisions import working_document
    from apps.events.website_projection import window
    if not page.draft_revision_id:
        return
    revision = page.draft_revision
    actual = working_document(page)
    expected = deepcopy(revision.document)
    profiles = {str(row.slot): row.profile_id for row in revision.member_references.all()}
    for section in actual["editorial_document"]["sections"]:
        if section["type"] == "team":
            for row in section["payload"]["entries"]:
                if row["kind"] == "member":
                    if profiles.get(row["id"]) != row.pop("profile_id"):
                        raise ImportVerificationError("Working member link does not match its typed draft reference.")
                    row["member_slot_id"] = row["id"]
    for section in expected["editorial_document"]["sections"]:
        if section["type"] == "team":
            section["payload"]["entries"] = [row for row in section["payload"]["entries"]
                if row["kind"] != "member" or profiles.get(row["member_slot_id"]) is not None]
    # Drafts saved before speaker order was pinned may hold heap order.
    for document in (actual, expected):
        for session in document["sessions"]:
            session["speakers"] = sorted(session["speakers"])
    encode = lambda value: json.dumps(value, sort_keys=True, default=lambda item: item.isoformat() if isinstance(item, datetime) else str(item))
    if encode(actual) != encode(expected) or revision.source_anchor_start != window(page.event or page.series)[0]:
        raise ImportVerificationError("Current working website and selected draft snapshot disagree.")
