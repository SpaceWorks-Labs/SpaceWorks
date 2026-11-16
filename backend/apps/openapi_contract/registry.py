"""One lookup over the deliberate contract exceptions, for the schema class and the guard."""
from .registry_bodyless import bodyless_keys
from .registry_payloads import EMPTY_SUCCESS, FREE_FORM

BODYLESS = bodyless_keys()


def contract_marks(view_key, method):
    """The `x-` extensions an operation carries because it is a listed exception."""
    key = (view_key, method.upper())
    marks = {}
    if key in BODYLESS:
        marks["x-request-body"] = "none"
    if key in FREE_FORM:
        marks["x-free-form"] = dict(FREE_FORM[key])
    if key in EMPTY_SUCCESS:
        marks["x-response-body"] = "none"
    return marks


def registered_keys():
    """Every listed (view, method), so the guard can report entries no operation uses."""
    return BODYLESS | frozenset(FREE_FORM) | frozenset(EMPTY_SUCCESS)
