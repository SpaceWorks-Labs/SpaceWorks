"""Reuse signed-provider fixtures; no real provider requests are permitted."""
from tests.p2_wa_meta.conftest import no_provider_network, wa as meta_wa
from tests.p2_wa_twilio.conftest import http, wa as twilio_wa

__all__ = ["http", "no_provider_network", "meta_wa", "twilio_wa"]
