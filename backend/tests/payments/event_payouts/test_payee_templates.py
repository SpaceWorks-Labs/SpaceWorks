"""Closed routing data and masked CSV checks, independent of a database."""

from datetime import UTC, datetime
import csv
import io
import unittest

from apps.payments.event_payouts.csv_values import COLUMNS, NUMERIC_COLUMNS, encode_rows, safe_cell
from apps.payments.event_payouts.templates import masked_details, validate_details
from apps.payments.event_payouts.validation import PayoutValidationError


class PayeeTemplates(unittest.TestCase):
    def validate(self, country, method, key, details):
        return validate_details(country=country, method=method, template=key, version=1,
                                details=details, enabled_templates={(country, method, key, 1)})

    def test_indian_bank_number_remains_a_string_with_leading_zeroes(self):
        result = self.validate("IN", "bank_transfer", "in_bank", {"holder_name": "Member", "account_number": "001234567890",
                               "ifsc": "SBIN0001234", "bank_name": "Bank"})
        self.assertEqual(result["account_number"], "001234567890")
        self.assertEqual(masked_details(result, country="IN", method="bank_transfer"), "••••7890")

    def test_upi_accepts_routing_identifier_but_refuses_pin(self):
        value = {"holder_name": "Member", "upi_id": "maker@bank"}
        self.validate("IN", "upi", "in_upi", value)
        with self.assertRaisesRegex(PayoutValidationError, "invalid_fields"):
            self.validate("IN", "upi", "in_upi", {**value, "pin": "1234"})

    def test_us_routing_checksum(self):
        value = {"holder_name": "Member", "routing_number": "021000021", "account_number": "001234567", "account_type": "checking"}
        self.validate("US", "bank_transfer", "us_bank", value)
        for routing in ("021000022", "000000000", "not-a-number"):
            with self.assertRaises(PayoutValidationError):
                self.validate("US", "bank_transfer", "us_bank", {**value, "routing_number": routing})

    def test_iban_checksum_length_country_and_swift_country(self):
        value = {"holder_name": "Member", "iban": "DE89 3704 0044 0532 0130 00", "swift": "COBADEFFXXX", "bank_name": "Bank"}
        result = self.validate("DE", "bank_transfer", "iban_bank", value)
        self.assertEqual(result["iban"], "DE89370400440532013000")
        for change in ({"iban": "DE89370400440532013001"}, {"iban": "GB82WEST12345698765432"}, {"swift": "COBAUSFFXXX"}):
            with self.assertRaises(PayoutValidationError):
                self.validate("DE", "bank_transfer", "iban_bank", {**value, **change})

    def test_only_explicitly_enabled_templates_can_collect_data(self):
        with self.assertRaisesRegex(PayoutValidationError, "payee_template_disabled"):
            validate_details(country="IN", method="cash", template="cash", version=1, details={"holder_name": "Member"}, enabled_templates=set())

    def test_tax_identifiers_documents_profile_saves_and_credentials_rejected(self):
        for key in ("pan", "tax_id", "w9", "tax_document", "password", "api_token", "save_choices", "profile_field_key"):
            with self.assertRaisesRegex(PayoutValidationError, "invalid_fields"):
                self.validate("IN", "cash", "cash", {"holder_name": "Member", key: "private"})

    def test_coercible_account_numbers_and_control_characters_refused(self):
        good = {"holder_name": "Member", "account_number": "001234567890", "ifsc": "SBIN0001234", "bank_name": "Bank"}
        for value in (123456, True, 1.2, "123\n456", "１２３４５６"):
            with self.assertRaises(PayoutValidationError):
                self.validate("IN", "bank_transfer", "in_bank", {**good, "account_number": value})

    def test_future_or_wrong_template_does_not_reinterpret_data(self):
        for changes in ({"version": 2}, {"version": True}, {"template": "in_bank"}):
            payload = {"country": "IN", "method": "cash", "template": "cash", "version": 1,
                       "details": {"holder_name": "Member"}, "enabled_templates": {("IN", "cash", "cash", 1)}}
            with self.assertRaisesRegex(PayoutValidationError, "payee_template_changed"):
                validate_details(**{**payload, **changes})

    def test_unknown_country_or_method_refused_without_echoing_data(self):
        for country, method in (("ZZ", "cash"), ([], "cash"), ("IN", []), ("US", "upi"), ("IN", "card_machine")):
            with self.assertRaises(PayoutValidationError) as caught:
                validate_details(country=country, method=method, template="cash", version=1,
                                 details={"holder_name": "Sensitive name"}, enabled_templates=set())
            self.assertNotIn("Sensitive name", str(caught.exception))


class MaskedCsv(unittest.TestCase):
    def row(self):
        row = {key: "opaque-reference" for key in COLUMNS}
        row.update({key: 100 for key in NUMERIC_COLUMNS})
        row.update(masked_payee="••••1234", currency="INR", exported_at=datetime(2026, 10, 18, tzinfo=UTC).isoformat())
        return row

    def test_spreadsheet_formulas_and_control_prefixes_neutralized(self):
        for value in ("=HYPERLINK(\"x\")", "+1", "-1", "@SUM(A1)", "  =1", "\t=1", "\n=1", "\ufeff=1"):
            self.assertTrue(safe_cell(value).startswith("'"), value)

    def test_closed_columns_reject_unmasked_fields(self):
        with self.assertRaisesRegex(PayoutValidationError, "invalid_csv_columns"):
            encode_rows([{**self.row(), "account_number": "001234567890"}])

    def test_masked_column_cannot_be_used_for_raw_bank_values(self):
        for raw in ("001234567890", "holder@example.com", "GB82WEST12345698765432"):
            with self.assertRaisesRegex(PayoutValidationError, "unmasked_csv_payee"):
                encode_rows([{**self.row(), "masked_payee": raw}])

    def test_csv_quotes_commas_and_formula_cells(self):
        value = self.row()
        value["event_title"] = '=HYPERLINK("x","y")'
        parsed = next(csv.DictReader(io.StringIO(encode_rows([value]))))
        self.assertEqual(parsed["event_title"], "'" + value["event_title"])
        self.assertEqual(parsed["masked_payee"], "••••1234")

    def test_numeric_columns_cannot_contain_formulas_or_float_values(self):
        for value in ("=1", 1.2, True, -1):
            with self.assertRaises(PayoutValidationError):
                encode_rows([{**self.row(), "approved_minor": value}])


if __name__ == "__main__":
    unittest.main()
