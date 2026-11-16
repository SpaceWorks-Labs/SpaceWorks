"""Decision 223 (d): what a guest-pass holder may do on a machine, by the space's machine mode.

The pass's frozen `machines` entitlement is one of:

* `none` -- no machine use (`guest_pass_no_machines`).
* `supervised` -- only inside an instructor's open supervised session
  (`supervised.may_use_supervised`). A supervisee's use is recorded by the instructor, so a
  self-service session or a job request is refused (`guest_pass_supervised_only`), and a
  supervisee who tries to start their own session is told so (`guest_pass_supervised_session`).
* `after_induction_cert` -- (name kept for stored passes; it now means "after access was granted")
  once the guest holds a machine access grant for the machine or its type (decision 319), else
  `guest_pass_machine_access_required`. An "open to all members" machine does not admit a guest.

Members never reach this module: the callers branch on `ActiveMemberPresence.guest_pass`.
"""
from django.utils import timezone
from django.utils.translation import gettext
from rest_framework.exceptions import APIException

from apps.makerspaces.guest_pass_queries import pass_entitlements


class GuestMachineRefused(APIException):
    """A 403 with a stable code, mirroring `SessionRefused` for surfaces that have none."""

    status_code = 403
    default_code = "guest_pass_no_machines"

    def __init__(self, code, detail):
        super().__init__({"detail": detail, "code": code}, code)
        self.code = code


def require_guest_machine(guest_pass, user, makerspace, *, machine=None, machine_type=None, surface="session", at=None):
    """Raise unless `guest_pass` allows `user` this machine use. `surface` is `session` or `job`."""
    from apps.machines.access_grants import can_use, can_use_type
    from apps.machines.supervised import may_use_supervised

    mode = pass_entitlements(guest_pass).machines
    moment = at or timezone.now()
    machine_type = machine_type or getattr(machine, "machine_type", None)
    if mode == "supervised":
        if surface == "session" and machine is not None and may_use_supervised(user, machine, moment):
            raise GuestMachineRefused(
                "guest_pass_supervised_session",
                gettext("You are using this machine inside a supervised session; your instructor records it."))
        raise GuestMachineRefused(
            "guest_pass_supervised_only",
            gettext("A guest may use machines only in an instructor's supervised session."))
    if mode == "after_induction_cert":
        if machine is not None:
            allowed, _reason = can_use(user, machine, now=moment, include_open=False)
        else:
            allowed, _reason = can_use_type(user, makerspace, machine_type, now=moment, include_open=False)
        if not allowed:
            raise GuestMachineRefused(
                "guest_pass_machine_access_required",
                gettext("A guest needs machine access from a space manager for this machine first."))
        return
    raise GuestMachineRefused("guest_pass_no_machines", gettext("Your guest pass does not include machine use."))
