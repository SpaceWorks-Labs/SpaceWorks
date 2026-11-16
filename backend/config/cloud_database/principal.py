"""Separate a provider's wire login from its actual SQL role identifier."""

from .connection import DatabaseConfigurationError


def database_principal(spec):
    host = spec.parameters["host"].lower()
    user = spec.parameters["user"]
    if host.endswith((".pooler.supabase.com", ".pooler.supabase.co")):
        role, separator, project = user.rpartition(".")
        if not separator or not role or not project.isascii() or not project.isalnum():
            raise DatabaseConfigurationError("Copy the shared-pooler login including its project suffix.")
        return role
    return user
