"""Retired module keys that are still READ as the module they were folded into.

Decision 340(b): the separate `printing` module ("a 3D print queue") is retired. Machine
service already takes service requests for every machine type -- 3D printers, lasers, CNC,
cutters -- so the printer queue is one machine type inside it, not a module of its own.

Retiring a key is not the same as forgetting it. A stored switch, a full-database backup
taken before the upgrade, a tenant dump from an older source and an API client written
against the old key list can all still say `printing`; each must keep meaning what it
meant. Every reader therefore canonicalizes through here: `printing` reads as
`machine_service`, which `printing` always required, so a space that had printing on
keeps exactly the surfaces it had. makerspaces/0154 rewrites the stored rows once; this map
covers everything that arrives later carrying the old key.

The same shape as `separability.tombstones.RENAMED_LABELS` (`payments` -> `payments_rail`).
A retired key is never in `module_registry.MODULE_KEYS`, so no screen, setup area, profile
or /features page can offer it.
"""

RETIRED_MODULE_ALIASES = {"printing": "machine_service"}


def canonical_module_key(key):
    """The live key a (possibly retired) module key means today; non-strings pass through
    untouched so the caller's own validation still reports them."""
    return RETIRED_MODULE_ALIASES.get(key, key) if isinstance(key, str) else key


def canonical_module_keys(keys):
    """Map every retired key to its live key, dropping duplicate strings, keeping first-seen order."""
    result = []
    for key in keys or ():
        key = canonical_module_key(key)
        if not (isinstance(key, str) and key in result):
            result.append(key)
    return result
