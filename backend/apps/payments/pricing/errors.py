"""Typed pricing errors: `{detail, code}` bodies with stable codes (lane L15)."""

from rest_framework import status
from rest_framework.exceptions import APIException


class PricingError(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    code = "pricing_error"
    message = "The price could not be worked out."

    def __init__(self, detail=None, **extra):
        body = {"detail": detail or self.message, "code": self.code, **extra}
        super().__init__(body, self.code)
        # Keep the body's real JSON types: DRF would stringify a nested quote (None -> "None").
        self.detail = body


class PricingDomainUnknown(PricingError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "pricing_domain_unknown"
    message = "That pricing area does not exist or is switched off."

    def __init__(self, domain=None):
        super().__init__(domain=domain)


class PricingDisabled(PricingError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "pricing_disabled"
    message = "Price lists are switched off for this space."


class ChargesOff(PricingError):
    """#184: the area's money is not tracked here (`charges.enabled` or `charges.<domain>` off),
    so it is free: nothing is priced, previewed or charged, and the route leaves no surface (#95)."""

    status_code = status.HTTP_404_NOT_FOUND
    code = "charges_off"
    message = "Charges are switched off for this area in this space, so it is free."

    def __init__(self, domain=None):
        super().__init__(domain=domain)


class ComponentNotAllowed(PricingError):
    code = "component_not_allowed"
    message = "That price component does not apply here."


class PriceChanged(PricingError):
    """A8: the price moved between the preview and the submit. Carries the new quote."""

    status_code = status.HTTP_409_CONFLICT
    code = "price_changed"
    message = "The price changed since you saw it. Check the new price and try again."


class ChargeExists(PricingError):
    status_code = status.HTTP_409_CONFLICT
    code = "charge_exists"
    message = "A charge has already been raised for this."


class DiscountInvalid(PricingError):
    code = "discount_invalid"
    message = "The discount is not valid."


class ReturnPhotoRequired(PricingError):
    status_code = status.HTTP_409_CONFLICT
    code = "return_photo_required"
    message = "A damage or lost charge needs the return photo that recorded the item."


class WaiverReasonRequired(PricingError):
    code = "waiver_reason_required"
    message = "Give a reason for waiving these fees."


class WaiverExists(PricingError):
    status_code = status.HTTP_409_CONFLICT
    code = "waiver_exists"
    message = "These fees are already waived on this loan."
