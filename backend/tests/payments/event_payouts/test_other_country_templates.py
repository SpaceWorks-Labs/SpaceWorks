import unittest
from apps.payments.event_payouts.templates import validate_details, masked_details
from apps.payments.event_payouts.validation import PayoutValidationError


class CountryTemplates(unittest.TestCase):
    def validate(self, country, template, details):
        return validate_details(country=country, method="bank_transfer", template=template, version=1,
            details=details, enabled_templates={(country, "bank_transfer", template, 1)})

    def test_australian_routing_preserves_leading_zeroes_and_masks_account(self):
        value = self.validate("AU", "au_bank", {"holder_name": "Holder", "bank_name": "Bank", "account_number": "00123456",
            "bsb": "012345", "swift": "CTBAAU2S"})
        self.assertEqual(value["account_number"], "00123456")
        self.assertEqual(masked_details(value, country="AU", method="bank_transfer"), "••••3456")

    def test_canadian_institution_and_transit_have_independent_widths(self):
        value = self.validate("CA", "ca_bank", {"holder_name": "Holder", "bank_name": "Bank", "account_number": "00123456",
            "institution_number": "001", "transit_number": "01234", "swift": "ROYCCAT2"})
        self.assertEqual(value["institution_number"], "001")
        with self.assertRaises(PayoutValidationError):
            self.validate("CA", "ca_bank", {**value, "transit_number": "123"})

    def test_tax_and_login_fields_never_enter_supported_templates(self):
        details = {"holder_name": "Holder", "bank_name": "Bank", "account_number": "00123456", "bsb": "012345", "swift": "CTBAAU2S"}
        for forbidden in ("password", "otp", "tax_id", "tax_document", "save_choices"):
            with self.assertRaises(PayoutValidationError):
                self.validate("AU", "au_bank", {**details, forbidden: "rejected"})

    def test_unsupported_country_does_not_fall_back_to_universal_routing(self):
        with self.assertRaises(PayoutValidationError):
            self.validate("ZZ", "bank", {})
