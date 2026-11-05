"""Fail when any API operation's OpenAPI contract is incomplete (CI `contracts` job).

    python manage.py openapi_contract_check

Generates the schema exactly as `spectacular` does and runs the guard in
`apps.openapi_contract.check`; prints one line per finding and exits non-zero on any.
"""
from django.core.management.base import BaseCommand, CommandError
from drf_spectacular.generators import SchemaGenerator

from drf_spectacular.drainage import GENERATOR_STATS

from apps.openapi_contract.check import component_collisions, contract_failures, live_view_keys, stale_entries


class Command(BaseCommand):
    help = "Check that every OpenAPI operation documents tags, security, bodies and errors."

    def handle(self, *args, **options):
        GENERATOR_STATS.reset()
        document = SchemaGenerator().get_schema(request=None, public=True)
        failures = contract_failures(document)
        failures += [("-", "components", f"two serializers share the component name {name}")
                     for name in component_collisions()]
        stale = stale_entries(live_view_keys())
        for method, path, problem in failures:
            self.stdout.write(f"{method} {path}: {problem}")
        for view, method in stale:
            self.stdout.write(f"stale contract exception: {view} {method}")
        operations = sum(1 for item in document["paths"].values() for key in item if key in
                         ("get", "post", "put", "patch", "delete"))
        if failures or stale:
            raise CommandError(f"{len(failures)} contract failures, {len(stale)} stale entries "
                               f"across {operations} operations.")
        self.stdout.write(self.style.SUCCESS(f"OpenAPI contract complete: {operations} operations."))
