"""A deleted connection takes its database login with it, once the delete commits."""

from django.db import transaction


def drop_login_after_delete(sender, instance, using="default", **kwargs):
    role = instance.login_role
    if not role:
        return
    from .provisioning import drop_login_quietly

    transaction.on_commit(lambda: drop_login_quietly(role, using), using=using)
