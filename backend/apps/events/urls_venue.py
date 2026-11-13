"""Decision 223 venue routes: the read-only venue panel and event creation with a room step."""
from django.urls import path

from .views_event_with_room import EventWithRoomView
from .views_room_choices import EventRoomChoicesView
from .views_venue_panel import EventVenuePanelView

patterns = [
    path("makerspace/<int:makerspace_id>/events/<int:event_id>/venue", EventVenuePanelView.as_view(),
         name="admin-event-venue"),
    path("makerspace/<int:makerspace_id>/events/with-room", EventWithRoomView.as_view(),
         name="admin-event-create-with-room"),
    path("makerspace/<int:makerspace_id>/event-room-choices", EventRoomChoicesView.as_view(),
         name="admin-event-room-choices"),
]
