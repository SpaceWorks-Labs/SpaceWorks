"""Which accounts /control/ lists: people and platform accounts, never inert shells.

One account per person: a retired or merged account is an inert shell kept only for its
history, so the account admin neither lists it nor opens it by id.
"""


def visible_staff_spaces():
    from apps.makerspaces.models import Makerspace
    from apps.makerspaces.servability import servable_q

    return Makerspace.objects.filter(servable_q())


def scope_account_rows(queryset):
    from apps.accounts.staff_identity import shell_q

    return queryset.exclude(shell_q())


def staff_account_hidden(user):
    from apps.accounts.staff_identity import is_shell

    return is_shell(user)
