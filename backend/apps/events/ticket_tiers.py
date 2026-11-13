"""Tier chaining (release 2 L6, G29): early bird, then regular, then late.

Ticket types that share a `tier_group` form a chain ordered by `tier_rank`. Only the
first LIVE tier of a chain is on sale: a tier stays live until it sells out or its sales
end, and only then does the next one open. A tier whose sales have not started yet is
still live, so it holds the later tiers back. Types without a group are never chained.
"""

from collections import defaultdict

from django.utils import timezone


def _chains(event):
    chains = defaultdict(list)
    for ticket in event.ticket_types.filter(is_active=True, purpose="participant").exclude(tier_group=""):
        chains[ticket.tier_group].append(ticket)
    return {group: sorted(rows, key=lambda row: (row.tier_rank, row.pk)) for group, rows in chains.items()}


def _finished(event, ticket, now):
    from .capacity import ticket_spots_left
    if ticket.sales_end_at is not None and ticket.sales_end_at <= now:
        return True
    return ticket.capacity > 0 and ticket_spots_left(event, ticket) == 0


def blocked_tiers(event, *, now=None):
    """Ids of chained tiers that are not open yet (an earlier tier is still live)."""
    now = now or timezone.now()
    blocked = set()
    for chain in _chains(event).values():
        live_seen = False
        for ticket in chain:
            if live_seen:
                blocked.add(ticket.pk)
            elif not _finished(event, ticket, now):
                live_seen = True
    return blocked


def open_tiers(event, rows):
    blocked = blocked_tiers(event)
    return rows.exclude(pk__in=blocked) if blocked else rows


def next_tier(event, ticket):
    """The tier that opens after `ticket` (for the "next tier" hint), or None."""
    if not ticket.tier_group:
        return None
    chain = _chains(event).get(ticket.tier_group, [])
    later = [row for row in chain if (row.tier_rank, row.pk) > (ticket.tier_rank, ticket.pk) and not row.is_hidden]
    return later[0] if later else None
