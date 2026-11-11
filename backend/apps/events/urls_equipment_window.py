"""Event equipment routes (picker, kits, desk) plus decision 221b: window availability, bulk plan, workshop machine unlink."""
from django.urls import path

from .views_equipment_desk import EventEquipmentDeskView
from .views_equipment_picker import EventEquipmentKitsView, EventEquipmentProductsView
from .views_equipment_window import EventEquipmentAvailabilityView, EventEquipmentPlanView
from .views_machine_booking_links import EventWorkshopMachineLinkView

_EVENT = "makerspace/<int:makerspace_id>/events/<int:event_id>/"

patterns = [
    path(_EVENT + "equipment-request-products", EventEquipmentProductsView.as_view(),
         name="event-equipment-request-products"),
    path(_EVENT + "equipment-kits", EventEquipmentKitsView.as_view(), name="event-equipment-kits"),
    path(_EVENT + "equipment-desk", EventEquipmentDeskView.as_view(), name="event-equipment-desk"),
    path(_EVENT + "workshop-machines/<int:link_id>", EventWorkshopMachineLinkView.as_view(),
         name="admin-event-workshop-machine-link"),
    path(_EVENT + "equipment-availability", EventEquipmentAvailabilityView.as_view(),
         name="event-equipment-availability"),
    path(_EVENT + "equipment-plan", EventEquipmentPlanView.as_view(), name="event-equipment-plan"),
]
