"""Remap only declared semantic paths, never arbitrary text/URL strings."""

from copy import deepcopy
from django.apps import apps
from apps.makerspaces.public_page_markdown import validate_markdown
from .insertion_errors import PrimaryKeyMapUnavailable
from .insertion_errors import ArchiveFormatError


def mapped(pk_map, label, value):
    return pk_map.lookup(apps.get_model(label), value)


def editorial(document, asset_label, pk_map, *, working=False):
    from apps.makerspaces.public_page_contract import normalize_document, validate_stored_document, empty_document
    kind = "makerspace" if asset_label.startswith("makerspaces.") else "event"
    data = deepcopy(document)
    if not data:
        data = empty_document(kind)
    if working:
        data = normalize_document(data, kind=kind)
    else:
        validate_stored_document(data, kind=kind)
    if data.get("cover_asset_id") is not None:
        data["cover_asset_id"] = mapped(pk_map, asset_label, data["cover_asset_id"])
    for section in data["sections"]:
        key, payload = section["type"], section["payload"]
        if key == "gallery":
            for item in payload["items"]:
                item["asset_id"] = mapped(pk_map, asset_label, item["asset_id"])
        elif key == "about":
            payload["markdown"] = validate_markdown(payload["markdown"])
        elif key == "team" and working:
            retained = []
            for item in payload["entries"]:
                if item["kind"] == "member":
                    try:
                        item["profile_id"] = mapped(pk_map, "makerspaces.MemberProfile", item["profile_id"])
                    except PrimaryKeyMapUnavailable:
                        continue
                retained.append(item)
            payload["entries"] = retained
        elif key == "stats":
            payload["publish_public_member_count"] = False
        elif key == "location":
            payload["enabled_publicly"] = False
    return data


def remap_documents(label, row, pk_map):
    if label in {"makerspaces.MakerspacePublicPageRevision", "events.EventPageRevision"} and row["schema_version"] != 1:
        raise ArchiveFormatError("Unsupported public-page snapshot schema version.")
    if label == "makerspaces.MakerspacePublicPageRevision":
        row["document"] = editorial(row["document"], "makerspaces.MakerspacePublicPageAsset", pk_map)
    elif label == "events.EventPage":
        row["editorial_document"] = editorial(row["editorial_document"], "events.EventPageAsset", pk_map, working=True)
        if "EDITORIAL" not in row["section_order"]:
            row["section_order"] = [*row["section_order"], "EDITORIAL"]
        row["section_enabled"] = {"EDITORIAL": True, **row["section_enabled"]}
    elif label == "events.EventPageRevision":
        document = deepcopy(row["document"])
        document["editorial_document"] = editorial(document["editorial_document"], "events.EventPageAsset", pk_map)
        for section in document["sections"]:
            if section.get("asset_id") is not None:
                section["asset_id"] = mapped(pk_map, "events.EventPageAsset", section["asset_id"])
            if section.get("body_rendering") != "legacy_literal_v1":
                validate_markdown(section["body"], legacy_http=True)
        for session in document["sessions"]:
            session["session_id"] = str(mapped(pk_map, "events.EventSessionIdentity", session["session_id"]))
            if session.get("body_rendering") != "legacy_literal_v1":
                validate_markdown(session["body"], legacy_http=True)
        row["document"] = document
