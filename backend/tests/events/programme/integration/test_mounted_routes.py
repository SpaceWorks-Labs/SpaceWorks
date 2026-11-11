"""Every installed lane route has one path and explicit per-method classification."""
from django.urls import reverse, resolve

from apps.accounts.programme_route_catalog import ROUTES


def test_all_programme_names_are_mounted_once():
    from apps.accounts.checks import all_routes
    from django.urls import get_resolver
    from collections import Counter
    counts = Counter(name for path, name in all_routes(get_resolver().url_patterns))
    for name, methods, target in ROUTES:
        assert counts[name] == 1, name


def test_full_schema_has_every_installed_route_operation():
    from drf_spectacular.generators import SchemaGenerator
    schema = SchemaGenerator().get_schema(request=None, public=True)
    from apps.accounts.checks import all_routes
    from django.urls import get_resolver
    import re
    names = {name: methods for name, methods, target in ROUTES}
    for path, name in all_routes(get_resolver().url_patterns):
        if name not in names:
            continue
        canonical = "/" + re.sub(r"<(?:[^:>]+:)?([^>]+)>", r"{\1}", path)
        # Spectacular normally coerces pk to id in the public schema.
        canonical = canonical.replace("{pk}", "{id}")
        assert canonical in schema["paths"], (name, canonical)
        for method in names[name]:
            if method != "HEAD":
                assert method.lower() in schema["paths"][canonical], (name, method)
