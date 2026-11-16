import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from apps.boxes.models import Box
from apps.inventory.models import InventoryProduct
from apps.makerspaces.models import Makerspace


pytestmark = pytest.mark.django_db


def make_makerspace(slug="main", name="Main Makerspace"):
    return Makerspace.objects.create(name=name, slug=slug)


def make_product(makerspace, name="Arduino Kit", box=None):
    return InventoryProduct.objects.create(
        makerspace=makerspace,
        name=name,
        box=box,
    )


def test_box_gets_auto_unique_code():
    makerspace = make_makerspace()

    box_one = Box.objects.create(makerspace=makerspace, label="A1")
    box_two = Box.objects.create(makerspace=makerspace, label="A2")

    assert box_one.code
    assert len(box_one.code) == 32
    assert box_one.code != box_two.code


def test_product_box_assignment_and_reverse_relation():
    makerspace = make_makerspace()
    box = Box.objects.create(makerspace=makerspace, label="A1")
    product = make_product(makerspace, box=box)

    assert product.box == box
    assert list(box.products.all()) == [product]


def test_duplicate_box_label_per_makerspace_raises_integrity_error():
    makerspace = make_makerspace()
    Box.objects.create(makerspace=makerspace, label="A1")

    with pytest.raises(IntegrityError), transaction.atomic():
        Box.objects.create(makerspace=makerspace, label="A1")


def test_product_clean_rejects_box_from_different_makerspace():
    makerspace = make_makerspace()
    other_makerspace = make_makerspace(slug="other", name="Other Makerspace")
    box = Box.objects.create(makerspace=other_makerspace, label="B1")
    product = InventoryProduct(makerspace=makerspace, name="Arduino Kit", box=box)

    with pytest.raises(ValidationError):
        product.clean()


def test_product_clean_allows_box_from_same_makerspace():
    makerspace = make_makerspace()
    box = Box.objects.create(makerspace=makerspace, label="A1")
    product = InventoryProduct(makerspace=makerspace, name="Arduino Kit", box=box)

    product.clean()


def test_box_clean_allows_parent_from_same_makerspace():
    makerspace = make_makerspace()
    parent = Box.objects.create(makerspace=makerspace, label="Parent")
    child = Box(makerspace=makerspace, label="Child", parent=parent)

    child.clean()


def test_box_clean_rejects_parent_from_different_makerspace():
    makerspace = make_makerspace()
    other_makerspace = make_makerspace(slug="other", name="Other Makerspace")
    parent = Box.objects.create(makerspace=other_makerspace, label="Parent")
    child = Box(makerspace=makerspace, label="Child", parent=parent)

    with pytest.raises(ValidationError):
        child.clean()


def test_box_clean_rejects_direct_self_parent():
    makerspace = make_makerspace()
    box = Box.objects.create(makerspace=makerspace, label="A1")
    box.parent = box

    with pytest.raises(ValidationError):
        box.clean()


def test_box_clean_rejects_two_cycle_parent():
    makerspace = make_makerspace()
    parent = Box.objects.create(makerspace=makerspace, label="Parent")
    child = Box.objects.create(makerspace=makerspace, label="Child", parent=parent)
    parent.parent = child

    with pytest.raises(ValidationError):
        parent.clean()
