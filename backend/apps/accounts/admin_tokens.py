"""Keep token revocation in the accounts token services.

Deleting a BlacklistedToken admin row un-revokes a refresh token.
"""

from django.contrib import admin
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken


for model in (BlacklistedToken, OutstandingToken):
    if admin.site.is_registered(model):
        admin.site.unregister(model)
