"""Staff principals are listed in /control/ only while their tenant can serve."""

from django.db.models import Q


def visible_staff_spaces():
    from apps.makerspaces.models import Makerspace
    from apps.makerspaces.servability import servable_q

    return Makerspace.objects.filter(servable_q())


def scope_account_rows(queryset):
    return queryset.filter(
        ~Q(account_kind="staff")
        | Q(staff_makerspace__in=visible_staff_spaces(), retired_at__isnull=True)
    )


def staff_account_hidden(user):
    return bool(user.account_kind == "staff" and (
        user.retired_at is not None
        or not visible_staff_spaces().filter(pk=user.staff_makerspace_id).exists()
    ))
