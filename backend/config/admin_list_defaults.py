"""List defaults every /control/ model list gets unless its admin says otherwise (0.12.0).

* 50 rows a page;
* a model with its own ``makerspace`` column is filterable by space, and that filter comes first;
* the foreign keys a list shows are joined in the same query (``select_related``), nullable ones
  included, so a list never runs one query per row for them.

An admin that sets ``list_filter`` with a space filter, or its own ``list_select_related``,
keeps exactly what it set.
"""

from django.core.exceptions import FieldDoesNotExist

PII_LIST_PREFIX = "pii_list__"


def _filter_name(entry):
    if isinstance(entry, str):
        return entry
    if isinstance(entry, (list, tuple)) and entry and isinstance(entry[0], str):
        return entry[0]
    return getattr(entry, "parameter_name", "") or ""


class ControlListDefaultsMixin:
    list_per_page = 50

    def _direct_makerspace(self):
        try:
            field = self.model._meta.get_field("makerspace")
        except FieldDoesNotExist:
            return False
        return bool(getattr(field, "concrete", False) and (field.many_to_one or field.one_to_one))

    def get_list_filter(self, request):
        filters = list(super().get_list_filter(request))
        if self._direct_makerspace() and not any(_filter_name(entry).startswith("makerspace") for entry in filters):
            filters.insert(0, "makerspace")
        return filters

    def get_list_select_related(self, request):
        chosen = super().get_list_select_related(request)
        if chosen is not False:
            return chosen
        names = []
        for name in self.get_list_display(request):
            if not isinstance(name, str):
                continue
            name = name.removeprefix(PII_LIST_PREFIX)
            try:
                field = self.model._meta.get_field(name)
            except FieldDoesNotExist:
                continue
            if getattr(field, "concrete", False) and (field.many_to_one or field.one_to_one):
                names.append(name)
        return tuple(names) or False
