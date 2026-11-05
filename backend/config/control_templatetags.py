"""Template filters for the /control/ copy (#188): `{% load control_copy %}`."""

from django import template

from config.control_catalog import help_for, title_for

register = template.Library()


@register.filter
def control_help(opts):
    """The plain-language line for a model's admin pages; "" for a model without one."""
    return help_for(getattr(opts, "label_lower", "")) if opts is not None else ""


@register.filter
def control_title(opts):
    return title_for(getattr(opts, "label_lower", "")) if opts is not None else ""
