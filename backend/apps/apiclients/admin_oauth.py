"""/control/ admins for django-oauth-toolkit's credential rows (#196), loaded by DOT itself.

DOT 3.4.1 already masks the token and code and refuses hand-made rows. Its change form still
lets an operator move a live token to another person or stretch its expiry, so these rows are
view-only here; revoking stays the one write (the "Revoke selected" action). DOT imports this
module from inside ``oauth2_provider.admin`` once its own classes are defined.
"""
from oauth2_provider.admin import AccessTokenAdmin, GrantAdmin, IDTokenAdmin, RefreshTokenAdmin


class _ViewOnly:
    def has_change_permission(self, request, obj=None):
        return False


class ViewOnlyAccessTokenAdmin(_ViewOnly, AccessTokenAdmin):
    pass


class ViewOnlyRefreshTokenAdmin(_ViewOnly, RefreshTokenAdmin):
    pass


class ViewOnlyGrantAdmin(_ViewOnly, GrantAdmin):
    pass


class ViewOnlyIDTokenAdmin(_ViewOnly, IDTokenAdmin):
    pass
