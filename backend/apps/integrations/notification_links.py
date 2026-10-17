"""Keep inbox navigation local and external transport links tenant-canonical."""
from urllib.parse import urlsplit

from apps.makerspaces.website_directory import public_url


def local_link(space, kind, tail=""):
    """Use the same verified-domain route mode as canonical external URLs."""
    url = urlsplit(public_url(space, kind, tail))
    path = url.path if tail else url.path.rstrip("/")
    return path + (f"?{url.query}" if url.query else "")


def external_links(space, rendered):
    from apps.notifications.inbox import safe_link

    value = dict(rendered)
    link = safe_link(value.get("link", ""))
    prefix = f"/m/{space.slug}/"
    if link.startswith(prefix):
        link = link[len(prefix) - 1:]
        owned = True
    else:
        owned = link.startswith(("/admin/", "/member/", "/items/")) or link in {"/admin", "/member"}
    if owned:
        kind, _, tail = link[1:].partition("/")
        value["link"] = public_url(space, kind, tail)
        if not tail:
            value["link"] = value["link"].rstrip("/")
    return value
