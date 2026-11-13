"""Definitions composed by scope_registry_routes without importing Django models."""


def routes(read, write, slug):
    return (
        ("public-presence-now", ("GET", "HEAD"), read, slug, False, False),
        ("public-presence-here-now", ("GET", "HEAD"), read, slug, False, False),
        ("public-machines-now", ("GET", "HEAD"), read, slug, False, False),
        ("public-presence-now-config", ("GET", "HEAD"), read, slug, False, False),
        ("presence-renew", ("POST",), write, slug, False, False),
        ("presence-projects", ("GET", "HEAD"), read, slug, False, False),
        ("presence-preferences", ("GET", "HEAD"), read, slug, False, False),
        ("presence-preferences", ("PATCH",), write, slug, False, False),
    )
