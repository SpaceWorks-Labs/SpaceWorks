import pytest
from apps.makerspaces.models import Makerspace
from tests.events.collab_helpers import make_staff


@pytest.fixture
def page_owner(settings):
    settings.INFRA_HOSTS = ["testserver", "localhost"]
    settings.PUBLIC_APP_BASE_URL = "http://testserver"
    space = Makerspace.objects.create(name="Page lab", slug="page-lab")
    return space, make_staff(space)


@pytest.fixture
def event_owner(settings):
    settings.INFRA_HOSTS = ["testserver", "localhost"]
    settings.PUBLIC_APP_BASE_URL = "http://testserver"
    from tests.events.ticketing_helpers import event_space, open_event
    space = event_space("page-event")
    space.enabled_features += ["events.website"]
    space.save(update_fields=["enabled_features"])
    return space, make_staff(space), open_event(space)
