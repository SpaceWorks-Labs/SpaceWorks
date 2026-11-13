from ._seed_demo_fixtures import seed_machine_service, seed_staff, seed_user

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import User
from apps.apiclients.models import ApiClient
from apps.boxes.models import Box
from apps.inventory.categories import ensure_default_categories
from apps.inventory.models import (
    Category,
    InventoryAsset,
    InventoryProduct,
    PublicAvailabilityMode,
    TrackingMode,
)
from apps.makerspaces.models import Makerspace
from apps.makerspaces.module_install import apply_profile
from apps.makerspaces.module_profiles import EVERYTHING
from apps.operations.seed_handles import claim_seeded_handles


DEMO_SPACES = [
    {
        "slug": "alpha-lab",
        "name": "Alpha Robotics Lab",
        "location": "Main Campus - Room A12",
        "manager": "alpha_manager",
    },
    {
        "slug": "beta-workshop",
        "name": "Beta Woodshop",
        "location": "North Wing - Woodshop",
        "manager": "beta_manager",
    },
    {
        "slug": "gamma-fab",
        "name": "Gamma Fabrication Studio",
        "location": "Downtown Fab Studio",
        "manager": "gamma_manager",
    },
]

DEMO_PRODUCTS = [
    ("Arduino Uno R4", "microcontrollers", 18, "Electronics Bay"),
    ("Soldering Station", "accessories", 6, "Repair Bench"),
    ("Cordless Drill Kit", "accessories", 4, "Tool Wall"),
    ("Digital Caliper", "sensors", 10, "Measurement Drawer"),
]


class Command(BaseCommand):
    help = "Seed demo superadmin, makerspaces, staff, boxes, and inventory."

    def add_arguments(self, parser):
        parser.add_argument(
            "--allow-production-demo",
            action="store_true",
            help="Explicitly allow fictional demo data in a production database.",
        )
        parser.add_argument(
            "--password",
            default="demo12345",
            help="Password applied to all demo staff accounts.",
        )

    def handle(self, *args, **options):
        if not settings.DEBUG and not options.get("allow_production_demo", False):
            raise CommandError(
                "seed_demo requires DEBUG=True or the explicit --allow-production-demo flag."
            )
        password = options["password"]
        superadmin = self._user(
            "superadmin",
            "superadmin@makerspace.local",
            password,
            User.Role.SUPERADMIN,
            is_staff=True,
            is_superuser=True,
        )

        spaces_created = 0
        products_written = 0
        assets_written = 0
        machine_services_written = 0
        for spec in DEMO_SPACES:
            makerspace, created = Makerspace.objects.update_or_create(
                slug=spec["slug"],
                defaults={
                    "name": spec["name"],
                    "location": spec["location"],
                    "public_inventory_enabled": True,
                    "created_by": superadmin,
                },
            )
            spaces_created += int(created)
            # Modules are opt-in, so a freshly created makerspace starts core-only and
            # the machine-service seed below would hit `require_module` and abort the
            # whole command. The demo data spans every module, so seed the `everything`
            # profile - but only on creation, so a re-run never rewrites the module set
            # of a space the operator has since tuned.
            if created:
                apply_profile(makerspace, EVERYTHING, actor=superadmin)
            ensure_default_categories(makerspace)
            seed_staff(makerspace, superadmin, spec["manager"], password)
            member = self._user(f"{makerspace.slug}_member", f"{makerspace.slug}-member@makerspace.local",
                                password, User.Role.REQUESTER)
            box = self._box(makerspace, "Starter Inventory", spec["location"])
            products_written += self._products(makerspace, box)
            assets_written += self._assets(makerspace, box)
            machine_services_written += self._machine_service(makerspace, member)

        self._sync_legacy_hmac_client()
        # Decision 308: a personal account without a username handle is blocked from every write (403
        # `handle_required`), so a fresh seed gives each account one (see operations/seed_handles.py).
        claim_seeded_handles()
        self.stdout.write(
            self.style.SUCCESS(
                "Seeded demo data: "
                f"spaces_created={spaces_created}, "
                f"products_written={products_written}, "
                f"assets_written={assets_written}, "
                f"machine_services_written={machine_services_written}. "
                "Accounts: superadmin, alpha_manager, beta_manager, gamma_manager."
            )
        )
        self.stdout.write(self.style.WARNING(f"Demo password for all accounts: {password}"))

    _user = staticmethod(seed_user)

    def _box(self, makerspace, label, location):
        box, _ = Box.objects.update_or_create(
            makerspace=makerspace,
            label=label,
            defaults={"location": location, "description": "Seeded demo storage."},
        )
        return box

    def _products(self, makerspace, box):
        categories = {
            category.slug: category
            for category in Category.objects.filter(makerspace=makerspace)
        }
        for name, category_slug, quantity, location in DEMO_PRODUCTS:
            InventoryProduct.objects.update_or_create(
                makerspace=makerspace,
                name=name,
                defaults={
                    "box": box,
                    "category": categories.get(category_slug),
                    "description": f"Demo stock for {makerspace.name}.",
                    "tracking_mode": TrackingMode.QUANTITY,
                    "total_quantity": quantity,
                    "available_quantity": quantity,
                    "reserved_quantity": 0,
                    "issued_quantity": 0,
                    "damaged_quantity": 0,
                    "lost_quantity": 0,
                    "needs_fix_quantity": 0,
                    "is_public": True,
                    "public_self_checkout_enabled": True,
                    "show_public_count": True,
                    "public_availability_mode": PublicAvailabilityMode.EXACT_COUNT,
                    "storage_location": location,
                    "is_archived": False,
                },
            )
        return len(DEMO_PRODUCTS)

    def _assets(self, makerspace, box):
        product, _ = InventoryProduct.objects.update_or_create(
            makerspace=makerspace,
            name="Oscilloscope Rigol DS1054Z",
            defaults={
                "box": box,
                "description": "Serialized demo lab instrument.",
                "tracking_mode": TrackingMode.INDIVIDUAL,
                "total_quantity": 3,
                "available_quantity": 3,
                "reserved_quantity": 0,
                "issued_quantity": 0,
                "damaged_quantity": 0,
                "lost_quantity": 0,
                "needs_fix_quantity": 0,
                "is_public": True,
                "public_self_checkout_enabled": False,
                "show_public_count": False,
                "public_availability_mode": PublicAvailabilityMode.STATUS_ONLY,
                "storage_location": "Instrument Cabinet",
                "is_archived": False,
            },
        )
        for index in range(1, 4):
            InventoryAsset.objects.update_or_create(
                makerspace=makerspace,
                asset_tag=f"{makerspace.slug.upper()}-OSC-{index:02d}",
                defaults={
                    "product": product,
                    "box": box,
                    "serial_number": f"DEMO-{makerspace.slug}-{index:02d}",
                    "status": InventoryAsset.Status.AVAILABLE,
                    "public_self_checkout_enabled": False,
                },
            )
        return 3

    _machine_service = staticmethod(seed_machine_service)

    def _sync_legacy_hmac_client(self):
        if not settings.HMAC_CLIENT_ID or not settings.HMAC_SECRET:
            return
        client = ApiClient.objects.filter(client_id=settings.HMAC_CLIENT_ID).first()
        if client is None:
            client = ApiClient(client_id=settings.HMAC_CLIENT_ID, label="Legacy frontend")
        client.allowed_origins = list(settings.CORS_ALLOWED_ORIGINS)
        client.set_secret(settings.HMAC_SECRET)
        client.save()
