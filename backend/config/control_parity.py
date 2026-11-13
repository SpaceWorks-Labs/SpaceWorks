"""#190 superadmin parity: every /control/ write has a web console path, or is host-only by design.

``/control/`` stays the server-only power tool and fallback (#189/#191). Day-to-day platform
work must not need it, so each operation it offers is listed here once:

* ``web(where, *routes)``: the web superadmin console does the same thing at ``where``,
  through the named API routes (the test checks each route name exists);
* ``host(where)``: deliberately server-side, and ``where`` tells the operator where to run it.
  Host-only is for: platform key rotation with the private key, whole-platform restore,
  recovery commands, and raw record repair of plumbing rows no workflow owns (sign-in
  lockout counters, OAuth protocol rows, quota counters, migration repair rows).

Keys: an admin model with any add/change/delete permission is ``"app.model"``; a list
action is ``"app.model.action"`` (Django's ``delete_selected`` is the model's own write);
a custom admin page is ``"view:<url name>"``; and the backup keys page's operations are
``"keys:<action>"``. ``tests/control_restructure_local/test_control_parity.py`` derives the
required keys from the live admin and fails on any missing or stale entry.
"""

from typing import NamedTuple


class Parity(NamedTuple):
    kind: str          # "web" or "host"
    where: str
    routes: tuple = ()


def web(where, *routes):
    return Parity("web", where, tuple(routes))


def host(where):
    return Parity("host", where)


SERVER = "/control/ over the SSH tunnel (or on the server itself)"
KEY_ROTATION = host("On the server: manage.py backup_keys (rotation with the private key), then /control/ → "
                    "Data & recovery → Backup keys, drills and notices")
RAW_REPAIR = host(f"Raw record repair, no workflow owns these rows: {SERVER}")
CONSOLE = "Web console"

from config.control_parity_entries import ENTRIES  # noqa: E402

PARITY = dict(ENTRIES)
# The /control/ backup keys page posts these `action` values (apps/backup/admin_keys.py).
KEYS_PAGE_OPERATIONS = ("rotate_platform", "rotate_server", "reencrypt", "purge", "reencrypt_all",
                        "reencrypt_stop", "settings")
