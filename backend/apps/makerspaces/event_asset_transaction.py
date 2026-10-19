"""Event asset writes: reserve, work without locks, replay and commit atomically.

The reservation pass validates the complete domain mutation in a rolled-back
transaction. Only the FK-free object intents survive it. Reserved primary keys
are reused by the final pass; no page, clone, revision or audit is visible early.
"""

from copy import deepcopy

from django.db import transaction
from rest_framework.exceptions import ValidationError

from .resource_clone import AssetCopies


class InspectImage(Exception):
    def __init__(self, storage, key):
        self.storage, self.key = storage, key


class EventAssetCopies(AssetCopies):
    def __init__(self):
        super().__init__()
        self.phase = "reserve"
        self.plans = []
        self.position = 0
        self.identities = {}
        self.snapshots = {}
        self.sizes = {}
        self.uploads = {}
        self.outer_atomic = transaction.get_connection().in_atomic_block

    def watch(self, name, value):
        if hasattr(value, "_meta"):
            value = {field.attname: getattr(value, field.attname)
                     for field in value._meta.concrete_fields}
        if name not in self.snapshots:
            self.snapshots[name] = deepcopy(value)
        elif self.snapshots[name] != value:
            raise ValidationError({"revision": "The source changed. Reload before retrying."})

    def remember(self, name, pk):
        self.identities.setdefault(name, pk)

    def create(self, name, model, **values):
        if name in self.identities:
            values["pk"] = self.identities[name]
        row = model.objects.create(**values)
        self.remember(name, row.pk)
        return row

    def copy_image(self, makerspace, image, *, storage, journal_page=None, expected_size=None):
        from .event_asset_work import plan_copy
        return plan_copy(self, makerspace, image, storage=storage,
                         page=journal_page, expected_size=expected_size)

    def upload(self, file, page):
        from .event_asset_work import plan_upload
        return plan_upload(self, file, page)

    def step(self, signature, reserve, *, page):
        if self.outer_atomic:
            raise RuntimeError("Event storage mutations require an outermost transaction boundary.")
        position = self.position
        self.position += 1
        if position == len(self.plans) and self.phase == "reserve":
            self.plans.append(reserve())
        if position >= len(self.plans) or self.plans[position]["signature"] != signature:
            raise ValidationError({"revision": "The source images changed. Reload before retrying."})
        plan = self.plans[position]
        if self.phase == "finalize":
            # Use the freshly locked owner and its CURRENT quota settings, not
            # a model instance cached by the reservation pass.
            plan["page"] = page
            from .website_asset_journal import finalize
            finalize(plan)
        return plan


def event_asset_transaction(operation):
    """Own both commits; refuse caller transactions which would retain locks."""
    from .event_asset_work import perform
    copies = EventAssetCopies()
    try:
        # The only unmeasured image is the legacy public event cover. Inspect it
        # outside atomic, then repeat validation before reserving any bytes.
        while True:
            copies.position = 0
            try:
                with transaction.atomic(durable=True):
                    result = operation(copies)
                    if not copies.plans:
                        transaction.on_commit(lambda: setattr(copies, "committed", True), robust=True)
                        return result
                    transaction.set_rollback(True)
                break
            except InspectImage as probe:
                if copies.outer_atomic:
                    raise RuntimeError("Event storage mutations require an outermost transaction boundary.")
                size = probe.storage.object_size(probe.key)
                copies.sizes[probe.key] = size
        for plan in copies.plans:
            perform(plan)
        copies.phase, copies.position = "finalize", 0
        with transaction.atomic(durable=True):
            transaction.on_commit(lambda: setattr(copies, "committed", True), robust=True)
            result = operation(copies)
            if copies.position != len(copies.plans):
                raise ValidationError({"revision": "The source images changed. Reload before retrying."})
        return result
    except BaseException:
        if not copies.committed:
            copies.cleanup()
        raise
