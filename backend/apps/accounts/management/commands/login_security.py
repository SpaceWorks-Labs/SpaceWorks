"""Host recovery for platform IP access, beside ``axes_reset_ip`` and ``recover_superadmin``.

    manage.py login_security --list
    manage.py login_security --allow 203.0.113.7 [--note "office"]
    manage.py login_security --unblock 203.0.113.7      (or --unblock all)

``--allow`` adds an ALLOW rule (allow beats every deny rule and automatic block), attributed
to the platform superadmin account and audited. ``--unblock`` lifts automatic blocks now,
one ``auth.ip_unblocked`` row each. A lockout by django-axes is separate: use
``axes_reset_ip`` / ``axes_reset_username`` for that.
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.accounts import ip_guard, ip_rules
from apps.accounts.admin_ip_access import unblock
from apps.accounts.login_security_contract import IP_ALLOW
from apps.accounts.models import IPAccessRule, IPAutoBlock, User
from apps.accounts.staff_identity import platform_q
from apps.audit import services as audit


class Command(BaseCommand):
    help = "List, allow or unblock platform IP access from the server shell."

    def add_arguments(self, parser):
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument("--list", action="store_true", help="Show the rules and the active automatic blocks.")
        group.add_argument("--allow", metavar="CIDR", help="Add an allow rule for an address or network.")
        group.add_argument("--unblock", metavar="IP|all", help="Lift the automatic block on an address, or all.")
        parser.add_argument("--note", default="Added with manage.py login_security", help="The rule's note.")

    def handle(self, *args, **options):
        if options["list"]:
            return self._list()
        if options["allow"]:
            return self._allow(options["allow"], options["note"][:200])
        return self._unblock(options["unblock"])

    def _list(self):
        for rule in IPAccessRule.objects.order_by("action", "cidr"):
            expiry = rule.expires_at.isoformat() if rule.expires_at else "never"
            self.stdout.write(f"rule  {rule.action:<5} {rule.cidr:<43} expires {expiry}  {rule.note}")
        for row in IPAutoBlock.objects.filter(blocked_until__gt=timezone.now()).order_by("blocked_until"):
            self.stdout.write(f"block {row.network:<49} until {row.blocked_until.isoformat()}")

    def _allow(self, value, note):
        try:
            cidr = ip_rules.canonical_cidr(value)
        except ValueError as exc:
            raise CommandError("Give an IP address or a network in CIDR form.") from exc
        owner = User.objects.filter(platform_q(), is_active=True).order_by("pk").first()
        if owner is None:
            raise CommandError("There is no platform superadmin account to own the rule; create it first.")
        with transaction.atomic():
            rule, created = IPAccessRule.objects.get_or_create(
                cidr=cidr, defaults={"action": IP_ALLOW, "note": note, "created_by": owner})
            if not created:
                rule.action, rule.expires_at, rule.note = IP_ALLOW, None, note
                rule.save(update_fields=["action", "expires_at", "note"])
            audit.record(None, "platform.ip_rule_saved", target=rule, meta={
                "via": "host_command", "created": created, "action": IP_ALLOW, "changed_fields": ["action"]})
        self.stdout.write(f"Allowed {cidr}.")

    def _unblock(self, value):
        if value == "all":
            rows = IPAutoBlock.objects.all()
        else:
            address = ip_rules.parse_address(value)
            if address is None:
                raise CommandError("Give an IP address, or 'all'.")
            rows = IPAutoBlock.objects.filter(ip_key=ip_guard.hmac_key("net", ip_guard.network_for(address)))
        with transaction.atomic():
            count = unblock(None, rows.select_for_update())
        self.stdout.write(f"Unblocked {count} address(es).")
