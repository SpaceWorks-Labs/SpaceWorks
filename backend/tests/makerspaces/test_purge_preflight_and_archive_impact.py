"""purge_module_data --preflight and the archive payout impact (local acceptance)."""
from io import StringIO
import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from apps.events.models import Event
from apps.makerspaces import lifecycle
from tests.makerspaces.test_module_purge import an_event, space, superadmin
from tests.module_helpers import disable_module

pytestmark = pytest.mark.django_db(transaction=True)


def test_preflight_prints_and_deletes_nothing():
    makerspace = space("preflight-events", "events")
    actor = superadmin("preflight-admin")
    an_event(makerspace)
    disable_module(makerspace, "events")
    out = StringIO()
    call_command("purge_module_data", "events", makerspace=makerspace.slug, actor=actor.username,
                 preflight=True, stdout=out)
    assert "Preflight for events: allowed" in out.getvalue()
    assert "preserved_core_obligations: 0" in out.getvalue()
    assert Event.objects.filter(makerspace=makerspace).exists()


def test_yes_still_runs_the_preflight_before_purging():
    makerspace = space("preflight-yes", "events")
    actor = superadmin("preflight-yes-admin")
    an_event(makerspace)
    disable_module(makerspace, "events")
    out = StringIO()
    call_command("purge_module_data", "events", makerspace=makerspace.slug, actor=actor.username, yes=True, stdout=out)
    assert out.getvalue().index("Preflight for events") < out.getvalue().index("Purged events")
    assert not Event.objects.filter(makerspace=makerspace).exists()


def test_preflight_refuses_an_installed_module():
    makerspace = space("preflight-installed", "events")
    actor = superadmin("preflight-installed-admin")
    with pytest.raises(CommandError):
        call_command("purge_module_data", "events", makerspace=makerspace.slug, actor=actor.username, preflight=True)


def test_archive_impact_counts_unpaid_event_payouts():
    makerspace = space("impact-space", "events")
    assert lifecycle.archive_impact(makerspace)["unpaid_event_payouts"] == 0
