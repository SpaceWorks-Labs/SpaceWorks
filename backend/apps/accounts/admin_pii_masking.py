"""Mask PII on /control/ list and change pages for a superadmin without an open window.

Presentation only (owner decision #111 Q12): the model, its form data and every workflow
keep the real values. A masked change page shows the PII fields read-only as dots and
leaves them out of the form, so saving the page cannot overwrite them either.

``pii_fields`` defaults to the scoped-encryption registry's fields for the model; an admin
adds account fields or its own display callables (such as a "requester" column that
prints a name) to ``pii_extra_fields``.
"""

from contextvars import ContextVar

from django.contrib import admin

from apps.accounts.pii_presentation import (
    ACCOUNT_PII_FIELDS, MASK, person_pii_visible, pii_makerspace_id, pii_visible, registry_field_names,
)
from apps.accounts.platform_authority import is_platform_superadmin

_VIEWER = ContextVar("pii_admin_viewer", default=None)
LIST_PREFIX, FORM_PREFIX = "pii_list__", "pii_masked__"


class PiiMaskingAdminMixin:
    pii_fields = None
    pii_extra_fields = ()

    def pii_field_names(self):
        base = self.pii_fields if self.pii_fields is not None else registry_field_names(self.model._meta.label)
        if self.model._meta.label == "accounts.User" and self.pii_fields is None:
            base = (*base, *ACCOUNT_PII_FIELDS)
        return (*base, *self.pii_extra_fields)

    def pii_row_visible(self, viewer, obj):
        if self.model._meta.label == "accounts.User":
            return person_pii_visible(viewer, obj)
        return pii_visible(viewer, pii_makerspace_id(obj))

    def __getattr__(self, name):
        # Generated display callables, resolved by name like any admin method.
        if name.startswith(LIST_PREFIX):
            return self._pii_list_display(name.removeprefix(LIST_PREFIX))
        if name.startswith(FORM_PREFIX):
            return self._pii_form_display(name.removeprefix(FORM_PREFIX))
        raise AttributeError(name)

    def _label(self, field):
        try:
            return self.model._meta.get_field(field).verbose_name
        except Exception:
            original = getattr(type(self), field, None)
            return getattr(original, "short_description", field.replace("_", " "))

    def _pii_list_display(self, field):
        def display(obj):
            viewer = _VIEWER.get()
            if viewer is not None and not self.pii_row_visible(viewer, obj):
                return MASK
            original = getattr(type(self), field, None)
            return original(self, obj) if callable(original) else getattr(obj, field)
        return admin.display(description=self._label(field))(display)

    def _pii_form_display(self, field):
        return admin.display(description=self._label(field))(lambda obj: MASK)

    def get_list_display(self, request):
        names = list(super().get_list_display(request))
        if not is_platform_superadmin(request.user):
            return names
        pii = set(self.pii_field_names())
        return [f"{LIST_PREFIX}{name}" if isinstance(name, str) and name in pii else name for name in names]

    def _masked_object(self, request, obj):
        return obj is not None and is_platform_superadmin(request.user) and not self.pii_row_visible(request.user, obj)

    def get_fieldsets(self, request, obj=None):
        fieldsets = super().get_fieldsets(request, obj)
        if not self._masked_object(request, obj):
            return fieldsets
        pii = set(self.pii_field_names())

        def swap(field):
            if isinstance(field, (list, tuple)):
                return tuple(swap(item) for item in field)
            return f"{FORM_PREFIX}{field}" if field in pii else field
        return [(name, {**options, "fields": tuple(dict.fromkeys(swap(field) for field in options.get("fields", ())))})
                for name, options in fieldsets]

    def get_readonly_fields(self, request, obj=None):
        fields = tuple(super().get_readonly_fields(request, obj))
        if not self._masked_object(request, obj):
            return fields
        # The raw names stay read-only too, so a declared form field can never be posted
        # (blank) over the stored value while the page shows dots.
        pii = sorted(set(self.pii_field_names()))
        return tuple(dict.fromkeys((*fields, *pii, *(f"{FORM_PREFIX}{field}" for field in pii))))

    def changelist_view(self, request, extra_context=None):
        token = _VIEWER.set(request.user)
        try:
            response = super().changelist_view(request, extra_context)
            if hasattr(response, "render") and not getattr(response, "is_rendered", True):
                response.render()
            return response
        finally:
            _VIEWER.reset(token)
