"""External venue fields (decision 295): a free-text address and an https map link on an event or series.

An organisation workspace often hosts events at a venue that is not a SpaceWorks space, so the address and
map link live on the event itself. They are public wherever the event is public; nothing else is derived.
"""

from urllib.parse import urlsplit

from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.utils.translation import gettext

ADDRESS_MAX = 500


def validate_map_url(value):
    """A public https link only: no other scheme, no userinfo, no spaces or control characters."""
    if not value:
        return
    try:
        URLValidator(schemes=["https"])(value)
        parsed = urlsplit(value)
    except (ValidationError, ValueError):
        raise ValidationError(gettext("Use a valid https map link.")) from None
    if parsed.username or parsed.password or any(ord(char) < 33 for char in value):
        raise ValidationError(gettext("Use a valid https map link."))
