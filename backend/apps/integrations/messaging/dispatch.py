"""Historical import shim. Domain adapters now emit canonical notification envelopes."""


def schedule_delivery(pk):
    """A stale legacy task cannot authorize a send or create a replacement intent."""
    return None


def enqueue_addressed_messages(*args, **kwargs):
    """Retained for old import sites; canonical source adapters own personal intents."""
    return []
