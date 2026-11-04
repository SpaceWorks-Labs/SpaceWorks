from django.core.management.base import BaseCommand, CommandError

from apps.tenant_rls.capabilities import CAPABILITIES
from apps.tenant_rls.checks import coverage_gaps
from apps.tenant_rls.policies import build_plans
from apps.tenant_rls.role_contract import status


class Command(BaseCommand):
    help = "Show the row-level security mode, runtime-role contract and policy coverage."

    def add_arguments(self, parser):
        parser.add_argument("--strict", action="store_true",
                            help="Exit non-zero unless every scoped table is policed and RLS is enforced.")

    def handle(self, *args, **options):
        state = status()
        contract = state["contract"]
        plans, unresolvable = build_plans()
        gaps = coverage_gaps()
        self.stdout.write(f"mode={state['mode']} configured={state['configured']}")
        if contract is not None:
            self.stdout.write(
                f"role={contract.role} superuser={contract.superuser} bypassrls={contract.bypassrls} "
                f"owns_scoped_tables={contract.owns_scoped_tables}")
        self.stdout.write(f"scoped_tables={len(plans)} missing_or_stale={len(gaps)} unresolvable={len(unresolvable)}")
        self.stdout.write("capabilities=" + ",".join(sorted(CAPABILITIES)))
        for table in gaps:
            self.stdout.write(f"gap {table}")
        if options["strict"] and (gaps or unresolvable or state["mode"] != "enforce"):
            raise CommandError("Row-level security is not fully enforced.")
