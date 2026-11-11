from types import SimpleNamespace
from uuid import uuid4
from tests.events.collab_helpers import make_staff
from tests.events.programme.contributions.helpers import setup_shift


def role_setup(settings):
    space, event, posting, shift, users, roles, adapter = setup_shift(settings)
    manager = make_staff(space)
    posting.permission_issuer = manager
    posting.save(update_fields=["permission_issuer"])
    adapter.forms = SimpleNamespace(
        prepare=lambda **kwargs: object(),
        apply_locked=lambda **kwargs: {"answers_json": '{"version":2,"answers":[]}', "schema_version": 2, "consent_revision": 5},
        require_approval_locked=lambda **kwargs: None,
        lock_locked=lambda **kwargs: None,
        reopen_locked=lambda **kwargs: None,
        review_date_locked=lambda **kwargs: None,
        export_owner=lambda **kwargs: {"subject_id": kwargs["subject"].subject_id},
    )
    return space, event, posting, shift, users, roles, adapter, manager


def command(row, **extra):
    return {"operation_id": uuid4(), "expected_version": row.version, **extra}
