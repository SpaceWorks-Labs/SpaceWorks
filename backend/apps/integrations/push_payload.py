"""Versioned native payload; links share the installed app's routing contract."""

from apps.integrations.mobile_link_contract import is_supported_link


def push_data(*, event_id, makerspace_id, feature, event, inbox_row_id=None, link=""):
    from apps.notifications.inbox import safe_link

    data = {"v": "2", "event_id": str(event_id), "makerspace_id": str(makerspace_id),
            "feature": str(feature), "event": str(event)}
    if inbox_row_id is not None:
        data["inbox_row_id"] = str(inbox_row_id)
    link = safe_link(link) if isinstance(link, str) else ""
    if link and is_supported_link(link):
        data["link"] = link
    return data
