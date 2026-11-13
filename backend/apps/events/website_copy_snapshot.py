"""Freeze the exact relational copy input across the lock-free storage window."""

from .models_website import EventSessionSpeaker


def watch_page(copies, page):
    copies.watch("source_page", page)
    copies.watch("source_page_owner", page.series if page.series_id else page.event)
    # Ownership/content writers serialize on the page/owner locks. Include
    # children as well as revision tokens so legacy relational writers cannot
    # silently change the graph whose bytes were reserved.
    for name in ("assets", "sections", "sessions", "session_identities", "session_aliases"):
        copies.watch("page_" + name, list(getattr(page, name).order_by("pk").values()))
    copies.watch("page_speakers", list(EventSessionSpeaker.objects.filter(
        session__page=page).order_by("pk").values()))
