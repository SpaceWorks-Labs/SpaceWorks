"""Tags by area: the fallback tag for views that name none, and ReDoc's tag groups.

A view's own `extend_schema(tags=...)` always wins; `fallback_tag` is consulted only when
a view states nothing, where drf-spectacular would otherwise file it under the first path
segment ("api"). `group_for` puts every tag into one area group (`x-tagGroups`, which
ReDoc renders as its side menu); a tag that fits no group is a contract failure, so a new
tag has to be placed on purpose.
"""
import re

_FALLBACK = tuple((re.compile(pattern), tag) for pattern, tag in (
    (r"^/api/v1/admin/events/\{[^}]+\}/(help|help-types|mentor-[a-z-]+|teams-export|teams-import)", "Event mentoring"),
    (r"^/api/v1/admin/events/\{[^}]+\}/(roles|shifts|shift-signups|volunteer-postings)", "Event roles"),
    (r"^/api/v1/member/makerspaces/\{[^}]+\}/events/\{[^}]+\}/(help|office-hours)", "Event mentoring"),
    (r"^/api/v1/member/makerspaces/\{[^}]+\}/events/\{[^}]+\}/(role-|shift)", "Event roles"),
    (r"^/api/v1/public/event-programmes/\{[^}]+\}/volunteer-postings", "Public events"),
    (r"^/api(/v1)?/public/\{[^}]+\}/inventory/", "Public inventory"),
    (r"^/api/v1/public/\{[^}]+\}/(machines|machine-types)", "Public machines"),
    (r"^/api/v1/admin/makerspaces/\{[^}]+\}/(machine-materials|machine-types)", "Admin machines"),
    (r"^/api/v1/admin/makerspaces/\{[^}]+\}/maintenance/", "Admin maintenance"),
    (r"^/api/v1/admin/makerspace/\{[^}]+\}/stocktake-", "Stocktake"),
    (r"^/api/v1/admin/makerspace/\{[^}]+\}/direct-loan-members", "Admin requests"),
    (r"^/api/v1/admin/inventory/", "Admin inventory"),
    (r"^/api/v1/admin/(evidence/|makerspaces/\{[^}]+\}/uploads/evidence-url)", "Evidence"),
))


def fallback_tag(path):
    for pattern, tag in _FALLBACK:
        if pattern.search(path):
            return tag
    return None


# (group, description, substrings), first match wins; matching is case-insensitive.
GROUPS = (
    ("Public API", "Anonymous and API-client routes: catalogue, events, pages, stats.",
     ("public", "embed", "server events", "server bookings")),
    ("Sign-in and accounts", "Sign-in, MFA, passkeys, devices and the person's account.",
     ("auth", "mfa", "passkey", "reauthentication", "account", "saved details", "mobile associations",
      "security settings")),
    ("Members", "What a signed-in member sees and does in a space.",
     ("member", "my cards", "personal notification", "memberships", "loans", "presence", "push")),
    ("Events", "Events, programmes, hackathons, tickets and their staff tools.",
     ("event", "sponsors", "card photos")),
    ("Bookings", "Bookable spaces, bookings and booking websites.", ("booking",)),
    ("Inventory and loans", "Inventory, QR, containers, stocktake, requests and procurement.",
     ("inventory", "bulk import", "qr ", "qr", "containers", "stock", "asset units", "admin requests",
      "procurement", "warranty", "evidence")),
    ("Machines and repairs", "Machines, machine jobs and sessions, printers, devices, kiosks, repairs.",
     ("machine", "printing", "repairs", "maintenance", "device", "kiosk")),
    ("Money", "Payments, pricing, the ledger, donations and the shop.",
     ("payment", "pricing", "finance", "ledger", "donation", "shop", "wallet")),
    ("ID cards", "Card designs, card jobs and ID programmes.", ("card", "id programmes")),
    ("Platform", "Superadmin and deployment-wide operations.",
     ("platform", "internal", "tenant", "backup", "hosting", "organizations", "health")),
    ("Space administration", "Settings, staff, notifications, integrations, reports and audit.",
     ("admin", "staff", "page editor", "email", "data exports", "notification", "messaging", "telegram",
      "whatsapp", "chat", "analytics", "reports", "dashboard", "api client", "api key", "integration",
      "audit", "pii", "makerspaces", "accountability")),
)


def group_for(tag):
    lowered = tag.lower()
    for group, _description, needles in GROUPS:
        if any(needle in lowered for needle in needles):
            return group
    return None


def add_tag_groups(result, generator, request, public):
    """drf-spectacular postprocessing hook: `x-tagGroups` covering every used tag."""
    used = sorted({tag for item in result.get("paths", {}).values() for operation in item.values()
                   if isinstance(operation, dict) for tag in operation.get("tags", ())})
    groups = {group: [] for group, _description, _needles in GROUPS}
    for tag in used:
        group = group_for(tag)
        if group is not None:
            groups[group].append(tag)
    result["x-tagGroups"] = [{"name": name, "tags": tags} for name, tags in groups.items() if tags]
    return result
