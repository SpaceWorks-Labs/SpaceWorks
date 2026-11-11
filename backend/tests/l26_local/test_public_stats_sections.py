"""L26 (#170): public stats sections, module gates, events privacy and suppression."""

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.bookings.models import BookableSpace, Booking
from apps.events.models import Event, EventRegistration
from apps.inventory.models import InventoryProduct, PublicAvailabilityMode
from apps.inventory.public_stats import build_public_stats
from apps.inventory.public_stats_period import suppressed
from apps.makerspaces.models import Makerspace, MakerspaceMembership
from apps.presence.models import PresenceSession

pytestmark = pytest.mark.django_db
from apps.makerspaces.module_registry import core_module_keys

ALL_MODULES = [*core_module_keys(), "events", "membership", "bookings", "presence", "machines"]


def space(slug, modules=ALL_MODULES, sections="events,machines,printing,lending,community", **fields):
    return Makerspace.objects.create(name=slug, slug=slug, public_inventory_enabled=True, public_stats_enabled=True,
                                     enabled_modules=list(modules), public_stats_sections=sections, **fields)


def url(makerspace):
    return reverse("v1:public-makerspace-stats", kwargs={"makerspace_slug": makerspace.slug})


def person(name):
    return User.objects.create_user(username=name, email=f"{name}@example.test", display_name=f"Secret {name}",
                                    access_status="active")


def event(makerspace, title, *, days=1, **values):
    start = timezone.now() + timedelta(days=days)
    values.setdefault("is_public", True)
    return Event.objects.create(makerspace=makerspace, title=title, status=values.pop("status", "published"),
                                starts_at=start, ends_at=start + timedelta(hours=2), **values)


def test_default_sections_keep_todays_page():
    makerspace = Makerspace.objects.create(name="d", slug="l26-default", enabled_modules=ALL_MODULES,
                                           public_stats_enabled=True)
    stats = build_public_stats(makerspace)
    assert stats["sections"] == ["machines", "lending"]  # printing needs machine_service + printing
    assert stats["events"] is None and stats["community"] is None
    assert stats["headline"] == [] and stats["tv"] == {"enabled": False, "refresh_seconds": 60}
    assert stats["period"]["key"] == "month"


def test_each_section_on_and_off_in_the_chosen_order():
    makerspace = space("l26-order", sections="community,lending,events")
    assert build_public_stats(makerspace)["sections"] == ["community", "lending", "events"]
    makerspace.public_stats_sections = "events"
    makerspace.save(update_fields=["public_stats_sections"])
    stats = build_public_stats(makerspace)
    assert stats["sections"] == ["events"]
    assert stats["hardware"] is None and stats["current_loans"] is None and stats["community"] is None
    assert {row["section"] for row in stats["metrics"]} == {"events"}


@pytest.mark.parametrize("module, section", [
    ("events", "events"), ("machines", "machines"), ("public_inventory", "lending"),
])
def test_module_off_hides_its_section_and_keeps_data(module, section):
    makerspace = space(f"l26-off-{module.replace('_', '-')}")
    event(makerspace, "Kept event")
    assert section in build_public_stats(makerspace)["sections"]
    makerspace.enabled_modules = [key for key in ALL_MODULES if key != module]
    makerspace.save(update_fields=["enabled_modules"])
    assert section not in build_public_stats(makerspace)["sections"]
    assert Event.objects.filter(makerspace=makerspace).exists()


def test_community_counts_follow_their_own_modules():
    makerspace = space("l26-community", modules=["membership"], sections="community")
    community = build_public_stats(makerspace)["community"]
    assert community["active_members"] == {"value": None, "suppressed": True}
    assert community["bookings"] is None and community["checkins"] is None
    makerspace.enabled_modules = []
    makerspace.save(update_fields=["enabled_modules"])
    assert build_public_stats(makerspace)["community"] is None


def test_page_404_when_off_or_nothing_left_to_show():
    client = APIClient()
    makerspace = space("l26-gate")
    assert client.get(url(makerspace)).status_code == 200
    makerspace.public_stats_enabled = False
    makerspace.save(update_fields=["public_stats_enabled"])
    assert client.get(url(makerspace)).status_code == 404
    makerspace.public_stats_enabled, makerspace.enabled_modules = True, []
    makerspace.save(update_fields=["public_stats_enabled", "enabled_modules"])
    assert client.get(url(makerspace)).status_code == 404
    makerspace.enabled_modules, makerspace.public_site_enabled = ALL_MODULES, False
    makerspace.save(update_fields=["enabled_modules", "public_site_enabled"])
    assert client.get(url(makerspace)).status_code == 404


def test_private_unlisted_invite_only_and_offline_events_never_appear():
    makerspace = space("l26-events", sections="events")
    event(makerspace, "Open jam")
    event(makerspace, "Private board", is_public=False)
    event(makerspace, "Unlisted test", listing=Event.Listing.UNLISTED)
    event(makerspace, "Invite dinner", registration_audience=Event.RegistrationAudience.INVITE)
    event(makerspace, "Offline page", page_state=Event.PageState.OFFLINE)
    event(makerspace, "Draft idea", status="draft")
    response = APIClient().get(url(makerspace))
    assert response.status_code == 200
    titles = [row["title"] for row in response.data["events"]["upcoming"]]
    assert titles == ["Open jam"]
    assert set(response.data["events"]["upcoming"][0]) == {"public_token", "title", "starts_at", "ends_at", "image_url"}
    body = response.content.decode()
    for hidden in ("Private board", "Unlisted test", "Invite dinner", "Offline page", "Draft idea"):
        assert hidden not in body


def test_events_held_and_attendees_count_only_listed_public_events():
    makerspace = space("l26-held", sections="events")
    held = [event(makerspace, f"Past {n}", days=0) for n in range(3)]
    for item in held:
        item.starts_at = timezone.now() - timedelta(minutes=5)
        item.save(update_fields=["starts_at"])
    hidden = event(makerspace, "Past private", days=0, is_public=False)
    hidden.starts_at = timezone.now() - timedelta(minutes=5)
    hidden.save(update_fields=["starts_at"])
    for index, item in enumerate(held + [hidden]):
        for n in range(2):
            EventRegistration.objects.create(event=item, member=person(f"att{index}{n}"), name="Secret Name",
                                             email=f"a{index}{n}@example.test", status=EventRegistration.Status.ATTENDED)
    section = build_public_stats(makerspace)["events"]
    assert section["held"] == {"value": 3, "suppressed": False}
    assert section["attendees"] == {"value": 6, "suppressed": False}


def test_small_number_suppression():
    assert suppressed(0) == suppressed(1) == suppressed(2) == {"value": None, "suppressed": True}
    assert suppressed(3) == {"value": 3, "suppressed": False}
    makerspace = space("l26-small", sections="community", public_stats_headline="community.bookings")
    now = timezone.now()

    def book(n):  # one room each: overlapping confirmed bookings in one room are refused
        room = BookableSpace.objects.create(makerspace=makerspace, name=f"Room {n}")
        Booking.objects.create(space=room, member=person(f"bk{n}"), name="Secret", email=f"b{n}@example.test",
                               phone="12345", starts_at=now - timedelta(minutes=30), ends_at=now, status="confirmed")
    for n in range(2):
        book(n)
    stats = build_public_stats(makerspace)
    assert stats["community"]["bookings"] == {"value": None, "suppressed": True}
    assert stats["headline"][0]["suppressed"] is True and stats["headline"][0]["value"] is None
    book(3)
    assert build_public_stats(makerspace)["community"]["bookings"] == {"value": 3, "suppressed": False}


def test_community_counts_members_and_checkins_without_names():
    makerspace = space("l26-members", sections="community")
    now = timezone.now()
    for n in range(4):
        user = person(f"mem{n}")
        MakerspaceMembership.objects.create(user=user, makerspace=makerspace, role="member",
                                            assigned_role=makerspace.roles.get(slug="member"))
        PresenceSession.objects.create(account=user, member=user, makerspace=makerspace, status="guest",
                                       started_at=now - timedelta(minutes=1), expires_at=now + timedelta(hours=1))
    response = APIClient().get(url(makerspace))
    community = response.data["community"]
    assert community["active_members"]["value"] == 4 and community["new_members"]["value"] == 4
    assert community["checkins"]["value"] == 4
    assert "Secret" not in response.content.decode() and "@example.test" not in response.content.decode()


def test_headline_picks_metrics_of_shown_sections_only():
    makerspace = space("l26-headline", sections="lending",
                       public_stats_headline="events.upcoming,lending.library,lending.loans")
    for n in range(3):
        InventoryProduct.objects.create(makerspace=makerspace, name=f"Tool {n}", is_public=True, total_quantity=1,
                                        available_quantity=1, public_availability_mode=PublicAvailabilityMode.EXACT_COUNT)
    headline = build_public_stats(makerspace)["headline"]
    assert [row["key"] for row in headline] == ["lending.library", "lending.loans"]
    assert headline[0]["value"] == 3 and headline[0]["label"] == "Tools in the library"


def test_response_is_cached_per_space_and_settings_change_is_a_new_key():
    client = APIClient()
    makerspace = space("l26-cache", sections="events")
    assert client.get(url(makerspace)).data["events"]["upcoming"] == []
    event(makerspace, "Fresh event")
    assert client.get(url(makerspace)).data["events"]["upcoming"] == []  # within the TTL
    makerspace.public_stats_period = "year"
    makerspace.save(update_fields=["public_stats_period"])
    assert [row["title"] for row in client.get(url(makerspace)).data["events"]["upcoming"]] == ["Fresh event"]


def test_edition_change_is_never_served_from_the_cache(settings):
    client = APIClient()
    makerspace = space("l26-edition", sections="machines,lending")
    assert client.get(url(makerspace)).status_code == 200
    settings.SPACEWORKS_EDITION = "events"
    assert client.get(url(makerspace)).status_code == 404
    makerspace.public_stats_sections = "events,lending"
    makerspace.save(update_fields=["public_stats_sections"])
    assert client.get(url(makerspace)).data["sections"] == ["events"]


def test_visibility_masks_legacy_values_metrics_and_headlines_server_side():
    makerspace = space("stats-granular-projection", sections="lending,events,community",
                       public_stats_headline="lending.library,events.held")
    for index in range(3):
        InventoryProduct.objects.create(makerspace=makerspace, name=f"Visible {index}",
                                        slug=f"visible-{index}", is_public=True)
    before = build_public_stats(makerspace)
    assert next(row for row in before["metrics"] if row["key"] == "lending.library")["value"] == 3
    makerspace.public_stats_config = {"visibility": {"lending.library": False, "events.upcoming_list": False,
                                                    "community.bookings": False, "lending.current_loans": False}}
    makerspace.save(update_fields=["public_stats_config"])
    after = build_public_stats(makerspace)
    assert after["hardware"]["library"]["library_size"] is None
    assert after["events"]["upcoming"] == [] and after["current_loans"] == []
    assert after["community"]["bookings"] is None
    assert all(row["key"] not in {"lending.library", "community.bookings"} for row in after["metrics"])
    assert all(row["key"] != "lending.library" for row in after["headline"])
    assert after["events"]["held"] == before["events"]["held"]  # suppression is unchanged
    assert after["visibility"]["lending.library"] is False


def test_all_widgets_hidden_removes_sections_without_deleting_or_reenabling_source_data():
    from apps.makerspaces.public_stats_catalogue import WIDGETS

    makerspace = space("stats-all-hidden")
    makerspace.public_stats_config = {"visibility": dict.fromkeys(WIDGETS, False)}
    makerspace.save(update_fields=["public_stats_config"])
    assert build_public_stats(makerspace)["sections"] == []
    assert APIClient().get(url(makerspace)).status_code == 404
    makerspace.public_stats_config["visibility"]["events.held"] = True
    makerspace.enabled_modules = [module for module in ALL_MODULES if module != "events"]
    makerspace.save(update_fields=["public_stats_config", "enabled_modules"])
    assert build_public_stats(makerspace)["sections"] == []
    makerspace.enabled_modules.append("events")
    makerspace.save(update_fields=["enabled_modules"])
    restored = build_public_stats(makerspace)
    assert restored["sections"] == ["events"]
    assert restored["events"]["held"] == suppressed(0)
    assert restored["events"]["upcoming"] == []
    assert makerspace.public_stats_config["visibility"]["events.held"] is True


def test_cache_key_changes_with_visibility_even_before_commit_invalidation():
    from apps.inventory.public_stats_cache import _key

    makerspace = space("stats-config-fingerprint")
    before = _key(makerspace)
    makerspace.public_stats_config = {"visibility": {"lending.current_loans": False}}
    assert _key(makerspace) != before


def test_catalogue_feature_off_hides_lending_but_workflow_off_keeps_public_product_counts():
    makerspace = space("stats-deep-source", sections="lending")
    InventoryProduct.objects.create(makerspace=makerspace, name="Public inventory", slug="stats-deep-public", is_public=True)
    makerspace.enabled_modules.remove("request_workflow")
    makerspace.save(update_fields=["enabled_modules"])
    stats = build_public_stats(makerspace)
    assert stats["sections"] == ["lending"] and stats["hardware"]["library"]["library_size"] == 1
    assert stats["current_loans"] == [] and stats["hardware"]["most_popular"] == []
    assert stats["visibility"]["lending.current_loans"] is False
    assert stats["visibility"]["lending.library"] is True
    assert all(row["key"] != "lending.loans" for row in stats["metrics"])
    makerspace.enabled_features = [key for key in makerspace.enabled_features if key != "loans.enabled"]
    makerspace.save(update_fields=["enabled_features"])
    assert build_public_stats(makerspace)["sections"] == []
    assert APIClient().get(url(makerspace)).status_code == 404
