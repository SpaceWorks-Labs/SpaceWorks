"""Typed conflicts for per-membership machine scope changes."""


class MemberMachineScopeConflict(Exception):
    """This membership is exempt or does not hold Machine Manager."""
