"""Keep inbox navigation local and external transport links tenant-canonical."""
from urllib.parse import urlsplit

from apps.makerspaces.website_directory import public_url


def local_link(space, kind, tail=""):
    """Use the same verified-domain route mode as canonical external URLs."""
    url = urlsplit(public_url(space, kind, tail))
    path = url.path if tail else url.path.rstrip("/")
    return path + (f"?{url.query}" if url.query else "")


def payment_link(space, *, external=False):
    """Ledger navigation survives archival; live spaces retain their canonical domain."""
    from apps.makerspaces.platform import member_payment_return_url

    url = member_payment_return_url(space)
    return url if external else urlsplit(url).path


def external_links(space, rendered):
    from apps.notifications.inbox import safe_link
    from django.utils.html import escape

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
        value["link"] = (payment_link(space, external=True) if link == "/member/archived"
                         else public_url(space, kind, tail))
        if not tail:
            value["link"] = value["link"].rstrip("/")
        # link is inbox metadata; outbound transports only consume body fields.
        navigation = value["link"]
        if navigation not in value.get("text", ""):
            value["text"] = f"{value.get('text', '').rstrip()}\n\n{navigation}"
        if value.get("html") and escape(navigation) not in value["html"]:
            value["html"] += f'<p><a href="{escape(navigation)}">Open in Space Works</a></p>'
    return value
