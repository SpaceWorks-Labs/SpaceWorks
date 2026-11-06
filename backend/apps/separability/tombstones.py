"""Deployment-level tombstoning of a separable app (plan B1/B5, decision D7).

Tombstoning is a **deployment** decision, not a per-makerspace one. URL routing,
admin registration and the OpenAPI schema are process-global: an app's runtime
surfaces are present for every tenant or absent for all of them. That is a
different question from the per-makerspace ``enabled_modules`` switch, which asks
whether a tenant uses a module the deployment ships — and the two compose, because
a module is usable only when both say yes.

``TOMBSTONED_APPS`` names **app labels, not module keys**. Several keys can share
one app (``printing``, ``machines`` and ``machine_service`` all live in
``apps.machines``), and it is the app's code that is being removed.

Tombstoning never touches data. Rows stay, migrations stay installed, and the
retention registry keeps its purge plans and PII mappings — see ``registry`` for
why deregistering those would strand private objects and plaintext PII. Reversing a
tombstone is deleting the label from the setting; nothing has to be restored.
"""

import os

from apps.separability.registry import register_runtime_app, registered_runtime_apps

# The apps that have been made separable, one per phase of plan B6. Declared rather
# than derived: separability is a decision about whether an app's surfaces can be
# removed without leaving the rest of the system incoherent, and nothing in the module
# registry encodes that. `is_core` comes closest and is not the same question --
# `apps.makerspaces` owns only non-core modules and is the tenant root, while
# `apps.inventory` owns a core module *and* two optional ones.
#
# Anything named in TOMBSTONED_APPS but absent here is refused at startup
# (separability.E007), so a typo, a dotted path or a core app cannot quietly read as a
# working tombstone.
SEPARABLE_APPS = frozenset({
    "procurement", "notifications", "warranty", "maintenance", "presence", "events", "bookings",
    # A deployment that takes no money online ships no provider surfaces: checkout,
    # the native payment sheet, Connect, refunds and every webhook. The LEDGER is not
    # here and cannot be tombstoned -- money owed, its receipts and its reconciliation
    # must stay readable and settleable on any deployment, which is exactly what
    # splitting `payments_rail` out of `payments` bought.
    "payments_rail", "event_reimbursements",
    # Superadmin-only release plumbing. A deployment updated by its own host tooling has
    # no use for the in-app control surface.
    # Deployments that never move tenants between servers ship none of these surfaces;
    # retained provenance rows remain readable and purgeable.
    "tenant_migration",
    # Enrolled printers/label printers: identity rows stay readable and purgeable.
    "devices",
    # Release 2 L3: organisation ID programmes (no module key; `membership.id_programmes`).
    "id_programmes",
    # Release 2 L22: the per-space shop (module key `shop`); sales stay in the core ledger.
    "shop",
})


# Every other first-party app, each with the reason it cannot be tombstoned (#183B(g)).
# Declared so a new app is a decision, not an accident: the local completeness test
# fails when an installed `apps.*` app sits in neither set. Analytics, managed hosting,
# space controls and the OAuth/token surfaces in `apiclients` are switched per space or
# per deployment by their own settings, not by removing their code.
CORE_APPS = {
    "accounts": "people, sign-in and RBAC: every request resolves through it",
    "makerspaces": "the tenant root, its module registry and settings authority",
    "organizations": "organisation accounts own spaces and programmes",
    "payments": "the money LEDGER must stay readable and settleable (donations live here as a capability)",
    "encryption": "scoped PII keys; tombstoning would strand ciphertext",
    "apiclients": "API clients, personal tokens and OAuth apps authenticate requests (off = no credentials issued)",
    "boxes": "core lending: box QR codes",
    "inventory": "core lending: items and availability math",
    "hardware_requests": "the request workflow state machine",
    "printing": "legacy print queue kept inside the machines stack",
    "audit": "append-only audit log",
    "evidence": "immutable handover evidence",
    "admin_api": "the staff console API every module mounts into",
    "data_export": "the classification registry every model must join",
    "integrations": "email, chat and notification delivery infrastructure",
    "operations": "reports, reminders, the scheduler and the platform overview",
    "machines": "machines, printing and machine service share one app",
    "roadmap": "the public roadmap page",
    "backup": "backups, restore and the deployment recovery gate",
    "hosting_requests": "the onboarding request queue (inert on self-host)",
    "card_designs": "the shared card engine used by member, event and programme cards",
    "tenant_rls": "the row-level-security backstop is never removed",
    "analytics": "per-space analytics logins; off unless a space turns the module on",
    "space_controls": "pause, read-only and schedules guard every write",
    "managed_hosting": "the limiter is dormant unless MANAGED_PLANS_ENABLED on a managed deployment",
    "separability": "this registry itself",
}


def unavailable_apps():
    """Separable apps this deployment does not ship, for clients that must hide UI.

    Most console tabs are gated by a module key, and `platform.available_modules`
    already drops a tombstoned app's key -- so most of the frontend needs nothing.
    This exists for the apps that own **no module key of their own**: `warranty` is
    gated by core `staff_admin` and `presence` by no module at all, so there is no key
    to drop and their tabs would survive the tombstone and 404 on every request. B5
    named warranty as the most exposed case for exactly this reason.

    Deployment-global, so it is emitted **omitted-when-empty**: an untombstoned
    deployment's payloads stay byte-for-byte what they were, the same discipline the
    `geofence_enabled` bootstrap flag follows.
    """
    from apps.separability.registry import runtime_active

    return sorted(app for app in SEPARABLE_APPS if not runtime_active(app))


#: Labels that have been renamed, mapped to what they mean now. A deployment's env is
#: written once and lives for years, so an existing `TOMBSTONED_APPS=payments` must keep
#: working rather than failing startup with separability.E007 on upgrade.
#:
#: `payments` -> `payments_rail` also carries the intent across faithfully. It always
#: meant "this deployment ships no online payment surfaces", and that is now exactly what
#: the rail label removes -- the difference is that the LEDGER stays, so such a
#: deployment gains readable receipts and offline reconciliation it should never have
#: been without.
RENAMED_LABELS = {"payments": "payments_rail"}


def tombstoned_app_labels():
    """Parse the deployment's tombstone list. The one parser; everything else reads it.

    Read from the environment rather than from settings because the earliest consumer
    is ``config/unfold.py``, which settings *imports* — it cannot import settings
    back. ``settings.TOMBSTONED_APPS`` is assigned from this function, so there is a
    single spelling of the parse and the two can never disagree.
    """
    raw = os.environ.get("TOMBSTONED_APPS", "")
    labels = {label.strip() for label in raw.split(",") if label.strip()}
    labels = {RENAMED_LABELS.get(label, label) for label in labels}
    if "events" in labels:
        labels.add("event_reimbursements")
    return frozenset(labels)


def app_is_tombstoned(app_label):
    """Read the setting directly, bypassing the runtime manifest.

    Almost every caller wants ``registry.runtime_active`` instead: it is the
    post-startup answer and it also knows about the permanently tombstoned apps that
    no setting names. Use this only where the manifest is not populated yet.

    That is a real case, not a hypothetical: ``django.contrib.admin`` sits above every
    ``apps.*`` entry in ``INSTALLED_APPS``, so its ``ready()`` autodiscovers every
    ``admin.py`` *before* the owning app's ``ready()`` has registered anything. An
    ``admin.py`` asking the manifest would be told "active" during a tombstoned boot
    and would register its models anyway. Both answers derive from the same setting,
    so they cannot disagree.
    """
    from django.conf import settings

    labels = getattr(settings, "TOMBSTONED_APPS", frozenset())
    return app_label in labels or (app_label == "event_reimbursements" and "events" in labels)


def register_separable_app(app_label):
    """Publish an app's runtime state into the manifest. Call from ``ready()``.

    Idempotent: ``ready()`` can run more than once in a process that reloads app
    configs, and duplicate registration is fatal by design.

    Query-free, as ``ready()`` requires — it reads one setting and touches no
    database.
    """
    if app_label in registered_runtime_apps():
        return
    register_runtime_app(app_label, tombstoned=app_is_tombstoned(app_label))
