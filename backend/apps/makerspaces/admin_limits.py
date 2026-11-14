"""Use the API quota contracts during Django admin form validation.

Django's changeform POST transaction keeps the makerspace lock acquired here until
the model and its inlines are saved. Checking in save_model instead would turn a
normal capacity refusal into a 500, after the form had already been accepted.
"""
from django import forms
from django.db import transaction
from rest_framework.exceptions import APIException

from apps.makerspaces import limits
from apps.makerspaces.models import Makerspace
from apps.managed_hosting.extra_quotas import check_extra_quota


def form_limit_error(exc):
    """Keep the API's translated message and stable code on a non-field error."""
    detail = exc.detail
    message = detail.get("detail", detail.get("limit"))
    return forms.ValidationError(str(message), code=str(detail["code"]))


def _counted(obj, key):
    if obj is None:
        return False
    if key == "products":
        return not obj.is_archived
    if key == "assets":
        return not obj.product.is_archived
    if key in {"machines", "api_clients", "boxes"}:
        return obj.is_active
    if key == "webhook_endpoints":
        return obj.channel == "webhook"
    if key == "stocktake_sessions_monthly":
        from apps.managed_hosting.extra_quota_counters import month_start

        return obj.started_at is None or obj.started_at >= month_start()
    return True


def check_admin_capacity(instance, key):
    """Check only a newly counted row: normal edits and retirement remain possible.

    Moving a counted row to another tenant and reactivating an uncounted row both
    consume a destination slot, just like a create. Unarchiving a product also
    restores its individual assets to the assets counter.
    """
    if not instance.makerspace_id:
        return
    with transaction.atomic():
        space = Makerspace.objects.select_for_update(no_key=True).get(pk=instance.makerspace_id)
        old = None if instance._state.adding else type(instance)._default_manager.filter(pk=instance.pk).first()
        same_space = old is not None and old.makerspace_id == space.pk
        adding = int(_counted(instance, key)) - int(same_space and _counted(old, key))
        if adding > 0:
            if key in {"products", "assets", "machines", "api_clients"}:
                limits.check_quota(space, key, adding=adding)
            else:
                check_extra_quota(space, key, adding=adding)
        if key == "products" and adding > 0 and old is not None:
            from apps.inventory.models import InventoryAsset

            assets = InventoryAsset.objects.filter(product=instance, makerspace=space).count()
            if assets:
                limits.check_quota(space, "assets", adding=assets)


class CapacityAdminMixin:
    """Opt in only the writable admin models that have a registered row quota."""
    quota_key = ""

    def get_form(self, request, obj=None, **kwargs):
        base = super().get_form(request, obj, **kwargs)
        key = self.quota_key

        class CapacityForm(base):
            def _post_clean(self):
                super()._post_clean()
                if self.errors:
                    return
                try:
                    check_admin_capacity(self.instance, key)
                except APIException as exc:
                    self.add_error(None, form_limit_error(exc))

        return CapacityForm
