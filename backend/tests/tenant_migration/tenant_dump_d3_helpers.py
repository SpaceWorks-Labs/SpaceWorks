from tests.account_split.sweep_helpers import (
    configured_membership as _configured_membership,
    create_test_user as _create_test_user,
    make_role_account as _make_role_account,
    role_slug as _role_slug,
)
from apps.accounts.models import User
from apps.backup.recipients_bech32 import convert_bits, encode
from apps.makerspaces.models import Makerspace, MakerspaceMembership


def makerspace(slug, *, modules=("notifications",)):
    return Makerspace.objects.create(name=slug, slug=slug, enabled_modules=list(modules))


def manager(space, suffix="manager", *, mailable=True, opted_in=True):
    user = _make_role_account(
        space,
        role_slug=_role_slug(MakerspaceMembership.Role.SPACE_MANAGER),
        username=f"{space.slug}-{suffix}",
        email=f"{space.slug}-{suffix}@example.com" if mailable else "",
        access_status=User.AccessStatus.ACTIVE,
    )
    _configured_membership(user=user, makerspace=space, receives_notifications=opted_in)
    return user


def operator(suffix="operator"):
    return _create_test_user(
        username=suffix,
        email=f"{suffix}@example.com",
        role=User.Role.SUPERADMIN,
        is_superuser=True,
        access_status=User.AccessStatus.ACTIVE,
    )


def recipient(space, seed):
    """A one-shot tenant age public key for an export (#111 Q7); nothing is stored."""
    del space
    return encode("age", convert_bits(bytes([seed]) * 32, 8, 5, pad=True))
