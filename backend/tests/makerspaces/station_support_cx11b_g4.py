"""Real station cookie and signed operator lease; no authentication or policy mocks."""
from types import SimpleNamespace

from cryptography.fernet import Fernet

from apps.accounts.models import User
from apps.hardware_requests.models import HardwareRequest, HardwareRequestItem
from apps.makerspaces import kiosk_station_services as stations, station_operator_leases as leases
from tests.modules.switch_matrix_object_helpers import object_world
from tests.return_helpers import make_product


def station_world(native, settings):
    settings.API_CLIENT_ENC_KEY = Fernet.generate_key().decode("ascii")
    settings.EVENT_STATION_PIN_PEPPER = "g4-independent-station-pepper-at-least-32-bytes"
    settings.CORS_ALLOWED_ORIGINS = ["https://g4-station.example.test"]
    space, client, objects = object_world(native)
    # The real station web origin must resolve to the selected tenant for native JWTs.
    space.frontend_domain = "g4-station.example.test"
    space.frontend_domain_status = "verified"
    space.save(update_fields=["frontend_domain", "frontend_domain_status"])
    actor = User.objects.get(username="sx-real-object-manager")
    station, credential, pin = stations.create_station(space, actor=actor, name="Retained desk", kind="handover")
    station, credential, session, cookie, expires = stations.start_session(credential.public_token, pin=pin)
    lease, token = leases.issue_lease(station=station, credential=credential, session_id=session,
                                     session_expires_at=expires, user=actor)
    client.cookies[stations.COOKIE_NAME] = cookie
    headers = {"HTTP_ORIGIN": "https://g4-station.example.test", "HTTP_X_STATION_CSRF": "1", "HTTP_X_KIOSK_OPERATOR_LEASE": token}
    product = make_product(space, available_quantity=9, reserved_quantity=1)
    row = HardwareRequest.objects.create(makerspace=space, requester=actor, requester_username=actor.username,
                                         requester_name="Retained operator", status="accepted")
    item = HardwareRequestItem.objects.create(request=row, product=product, requested_quantity=1, accepted_quantity=1)
    return SimpleNamespace(space=space, client=client, user=actor, station=station, credential=credential,
        lease=lease, headers=headers, request=row, product=product, item=item, box=objects["box"])
