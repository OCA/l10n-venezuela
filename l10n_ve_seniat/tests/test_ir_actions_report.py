# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields
from odoo.tests import tagged

from .common import L10nVeSeniatCommon


@tagged("post_install", "-at_install")
class TestIrActionsReport(L10nVeSeniatCommon):
    def test_render_qweb_pdf_marks_original_printed(self):
        journal = self.company_data["default_journal_sale"]
        journal.l10n_ve_emission_medium = "free"
        journal.l10n_ve_free_form_print_medium = "pdf"
        partner = self.env["res.partner"].create(
            {
                "name": "Partner",
                "country_id": self.env.ref("base.ve").id,
                "vat": "J12345678",
            }
        )
        move = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": partner.id,
                "invoice_date": fields.Date.today(),
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Line",
                            "quantity": 1.0,
                            "price_unit": 100.0,
                            "account_id": self.company_data[
                                "default_account_revenue"
                            ].id,
                            "tax_ids": [
                                (6, 0, [self.company_data["default_tax_sale"].id])
                            ],
                        },
                    )
                ],
            }
        )
        move.action_post()
        report = self.env.ref("account.account_invoices", raise_if_not_found=False)
        if report:
            report.with_context(l10n_ve_invoice=True)._render_qweb_pdf(
                report.report_name, move.ids
            )
            move.invalidate_recordset()
            self.assertTrue(move.l10n_ve_invoice_original_printed)
            self.assertTrue(move.invoice_pdf_report_id)

    def test_invoice_report_uses_book_paperformat(self):
        book = self.env["account.book"].search(
            [("name", "=", "Talonario tests")], limit=1
        )
        self.assertTrue(book.paperformat_id)
        book.write({"l10n_ve_invoice_header_spacing": 42})
        book.paperformat_id.invalidate_recordset()
        self.assertEqual(book.paperformat_id.header_spacing, 42)

        partner = self.env["res.partner"].create(
            {
                "name": "Partner PF",
                "country_id": self.env.ref("base.ve").id,
                "vat": "J12345679",
            }
        )
        move = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": partner.id,
                "invoice_date": fields.Date.today(),
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Line",
                            "quantity": 1.0,
                            "price_unit": 50.0,
                            "account_id": self.company_data[
                                "default_account_revenue"
                            ].id,
                            "tax_ids": [
                                (6, 0, [self.company_data["default_tax_sale"].id])
                            ],
                        },
                    )
                ],
            }
        )
        move.action_post()
        self.assertEqual(move._l10n_ve_get_invoice_paperformat(), book.paperformat_id)

        report = self.env.ref("account.account_invoices", raise_if_not_found=False)
        if report:
            report = report.with_context(
                l10n_ve_book_paperformat_id=book.paperformat_id.id
            )
            self.assertEqual(report.get_paperformat(), book.paperformat_id)

    def test_get_valid_action_reports_keeps_alternate_reports_without_original_print(
        self,
    ):
        report = self.env.ref(
            "account.account_invoices_without_payment", raise_if_not_found=False
        )
        if not report:
            return
        partner = self.env["res.partner"].create(
            {
                "name": "Partner Alt Report",
                "country_id": self.env.ref("base.ve").id,
                "vat": "J12345681",
            }
        )
        move = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": partner.id,
                "invoice_date": fields.Date.today(),
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Line",
                            "quantity": 1.0,
                            "price_unit": 100.0,
                            "account_id": self.company_data[
                                "default_account_revenue"
                            ].id,
                            "tax_ids": [
                                (6, 0, [self.company_data["default_tax_sale"].id])
                            ],
                        },
                    )
                ],
            }
        )
        report.write({"binding_model_id": self.env["ir.model"]._get("account.move").id})
        move.action_post()
        self.assertFalse(move.l10n_ve_invoice_original_printed)
        valid_ids = report.get_valid_action_reports("account.move", move.ids)
        self.assertIn(report.id, valid_ids)

    def test_get_valid_action_reports_hides_original_invoice_pdf_until_allowed(self):
        original_report = self.env.ref(
            "account.account_invoices", raise_if_not_found=False
        )
        alternate_report = self.env.ref(
            "account.account_invoices_without_payment", raise_if_not_found=False
        )
        if not original_report or not alternate_report:
            return
        journal = self.company_data["default_journal_sale"]
        journal.l10n_ve_emission_medium = "free"
        journal.l10n_ve_free_form_print_medium = "pdf"
        partner = self.env["res.partner"].create(
            {
                "name": "Partner Draft",
                "country_id": self.env.ref("base.ve").id,
                "vat": "J12345680",
            }
        )
        move = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": partner.id,
                "invoice_date": fields.Date.today(),
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Line",
                            "quantity": 1.0,
                            "price_unit": 100.0,
                            "account_id": self.company_data[
                                "default_account_revenue"
                            ].id,
                            "tax_ids": [
                                (6, 0, [self.company_data["default_tax_sale"].id])
                            ],
                        },
                    )
                ],
            }
        )
        original_report.write(
            {"binding_model_id": self.env["ir.model"]._get("account.move").id}
        )
        alternate_report.write(
            {"binding_model_id": self.env["ir.model"]._get("account.move").id}
        )
        valid_ids = original_report.get_valid_action_reports("account.move", move.ids)
        self.assertNotIn(original_report.id, valid_ids)
        valid_ids = alternate_report.get_valid_action_reports("account.move", move.ids)
        self.assertIn(alternate_report.id, valid_ids)
        move.action_post()
        self.assertFalse(move.l10n_ve_invoice_original_printed)
        valid_ids = original_report.get_valid_action_reports("account.move", move.ids)
        self.assertNotIn(original_report.id, valid_ids)
        valid_ids = alternate_report.get_valid_action_reports("account.move", move.ids)
        self.assertIn(alternate_report.id, valid_ids)
        move.l10n_ve_invoice_original_printed = True
        valid_ids = original_report.get_valid_action_reports("account.move", move.ids)
        self.assertIn(original_report.id, valid_ids)

    def test_get_valid_action_reports_allows_native_without_emission_medium(self):
        original_report = self.env.ref(
            "account.account_invoices", raise_if_not_found=False
        )
        if not original_report:
            return
        journal = self.company_data["default_journal_sale"]
        journal.write(
            {
                "l10n_ve_emission_medium": False,
                "l10n_ve_invoice_section_id": False,
                "l10n_ve_credit_note_section_id": False,
                "l10n_ve_debit_note_section_id": False,
            }
        )
        partner = self.env["res.partner"].create(
            {
                "name": "Partner No Medium",
                "country_id": self.env.ref("base.ve").id,
                "vat": "J12345682",
            }
        )
        move = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": partner.id,
                "invoice_date": fields.Date.today(),
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Line",
                            "quantity": 1.0,
                            "price_unit": 100.0,
                            "account_id": self.company_data[
                                "default_account_revenue"
                            ].id,
                            "tax_ids": [
                                (6, 0, [self.company_data["default_tax_sale"].id])
                            ],
                        },
                    )
                ],
            }
        )
        original_report.write(
            {"binding_model_id": self.env["ir.model"]._get("account.move").id}
        )
        move.action_post()
        self.assertFalse(move.l10n_ve_journal_emission_medium)
        self.assertFalse(move.l10n_ve_invoice_original_printed)
        valid_ids = original_report.get_valid_action_reports("account.move", move.ids)
        self.assertIn(original_report.id, valid_ids)
