"""Keep inbox navigation local and external transport links tenant-canonical."""
from apps.makerspaces.website_directory import public_url
from apps.notifications.inbox import safe_link


def external_links(space, rendered):
    value = dict(rendered)
    link = safe_link(value.get("link", ""))
    prefix = f"/m/{space.slug}/"
    if link.startswith(prefix):
        kind, separator, tail = link[len(prefix):].partition("/")
        if separator:
            value["link"] = public_url(space, kind, tail)
    return value
