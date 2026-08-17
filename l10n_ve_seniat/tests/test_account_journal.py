# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.exceptions import ValidationError
from odoo.tests import tagged

from .common import L10nVeSeniatCommon


@tagged("post_install", "-at_install")
class TestAccountJournal(L10nVeSeniatCommon):
    def test_sale_journal_fiscal_section_fields_default_false(self):
        journal = self.env["account.journal"].create(
            {
                "name": "Test Sale Journal",
                "type": "sale",
                "code": "TSAL",
                "company_id": self.env.company.id,
            }
        )
        self.assertFalse(journal.l10n_ve_invoice_section_id)
        self.assertFalse(journal.l10n_ve_credit_note_section_id)
        self.assertFalse(journal.l10n_ve_debit_note_section_id)

    def test_l10n_ve_section_other_company_raises(self):
        company_b = self.env["res.company"].create({"name": "Empresa B VE Test"})
        book_b = self.env["account.book"].create(
            {
                "name": "Talonario B",
                "company_id": company_b.id,
                "number_from": 1,
                "number_to": 1000,
            }
        )
        section_b = self.env["account.book.section"].create(
            {
                "book_id": book_b.id,
                "name": "Tramo B",
                "number_from": 1,
                "number_to": 1000,
            }
        )
        journal = self.company_data["default_journal_sale"]
        with self.assertRaises(ValidationError):
            journal.write({"l10n_ve_invoice_section_id": section_b.id})

    def test_free_form_print_medium_default_pdf(self):
        journal = self.company_data["default_journal_sale"]
        self.assertEqual(journal.l10n_ve_free_form_print_medium, "pdf")

    def test_continuous_print_requires_free_emission(self):
        journal = self.company_data["default_journal_sale"]
        with self.assertRaises(ValidationError):
            journal.write(
                {
                    "l10n_ve_emission_medium": "digital",
                    "l10n_ve_free_form_print_medium": "continuous",
                }
            )

    def test_journal_line_limits_disabled_by_default(self):
        journal = self.company_data["default_journal_sale"]
        self.assertFalse(journal.l10n_ve_limit_invoice_lines)
        self.assertFalse(journal.l10n_ve_limit_picking_lines)
        self.assertFalse(journal.l10n_ve_max_invoice_lines)
        self.assertFalse(journal.l10n_ve_max_picking_lines)
        self.assertEqual(journal._l10n_ve_journal_invoice_line_limit(), 0)
        self.assertEqual(journal._l10n_ve_journal_picking_line_limit(), 0)

    def test_journal_line_limits_when_enabled(self):
        journal = self.company_data["default_journal_sale"]
        journal.write(
            {
                "l10n_ve_emission_medium": "digital",
                "l10n_ve_limit_invoice_lines": True,
                "l10n_ve_max_invoice_lines": 5,
                "l10n_ve_limit_picking_lines": True,
                "l10n_ve_max_picking_lines": 8,
            }
        )
        self.assertEqual(journal._l10n_ve_journal_invoice_line_limit(), 5)
        self.assertEqual(journal._l10n_ve_journal_picking_line_limit(), 8)

    def test_journal_line_limits_without_emission_medium(self):
        journal = self.company_data["default_journal_sale"]
        journal.write(
            {
                "l10n_ve_emission_medium": False,
                "l10n_ve_limit_invoice_lines": True,
                "l10n_ve_max_invoice_lines": 3,
                "l10n_ve_limit_picking_lines": True,
                "l10n_ve_max_picking_lines": 4,
            }
        )
        self.assertEqual(journal._l10n_ve_journal_invoice_line_limit(), 3)
        self.assertEqual(journal._l10n_ve_journal_picking_line_limit(), 4)

    def test_journal_line_limits_require_value_when_enabled(self):
        journal = self.company_data["default_journal_sale"]
        with self.assertRaises(ValidationError):
            journal.write(
                {
                    "l10n_ve_emission_medium": "digital",
                    "l10n_ve_limit_invoice_lines": True,
                    "l10n_ve_max_invoice_lines": 0,
                }
            )
        with self.assertRaises(ValidationError):
            journal.write(
                {
                    "l10n_ve_emission_medium": "digital",
                    "l10n_ve_limit_picking_lines": True,
                    "l10n_ve_max_picking_lines": 0,
                }
            )
