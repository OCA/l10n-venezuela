# Copyright 2026 BWEALTHICS LLC
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from unittest.mock import patch

from odoo import Command, fields
from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged("post_install", "-at_install")
class TestInvoiceFormat(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.company_data["company"]
        cls.tax_16 = cls.env["account.tax"].create(
            {
                "name": "Test VAT 16%",
                "amount": 16.0,
                "amount_type": "percent",
                "type_tax_use": "sale",
                "company_id": cls.company.id,
            }
        )
        cls.tax_exempt = cls.env["account.tax"].create(
            {
                "name": "Test Exempt Sale",
                "amount": 0.0,
                "amount_type": "percent",
                "type_tax_use": "sale",
                "company_id": cls.company.id,
            }
        )
        partner = (
            cls.env["res.partner"]
            .with_context(no_vat_validation=True)
            .create(
                {
                    "name": "Venezuelan Customer",
                    "vat": "J-12345678-9",
                    "country_id": cls.env.ref("base.ve").id,
                }
            )
        )
        cls.invoice = cls.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": partner.id,
                "invoice_date": fields.Date.to_date("2026-07-25"),
                "l10n_ve_control_number": "00-00001234",
                "l10n_ve_control_date": fields.Date.to_date("2026-07-25"),
                "invoice_line_ids": [
                    Command.create(
                        {
                            "name": "Taxed Product",
                            "quantity": 1.0,
                            "price_unit": 100.0,
                            "tax_ids": [Command.set(cls.tax_16.ids)],
                        }
                    ),
                    Command.create(
                        {
                            "name": "Exempt Product",
                            "quantity": 1.0,
                            "price_unit": 50.0,
                            "tax_ids": [Command.set(cls.tax_exempt.ids)],
                        }
                    ),
                ],
            }
        )
        cls.company.country_id = cls.env.ref("base.ve")
        cls.company.account_fiscal_country_id = cls.env.ref("base.ve")
        cls.company_data["default_journal_sale"].l10n_ve_emission_medium = "free"
        cls.invoice.action_post()

    def _render_invoice(self, invoice=None):
        invoice = invoice or self.invoice
        return (
            self.env["ir.actions.report"]
            ._render_qweb_html("account.report_invoice", invoice.ids)[0]
            .decode()
        )

    def _setup_bs(self, rate=100.0):
        bs_currency = (
            self.env["res.currency"]
            .with_context(active_test=False)
            .search([("name", "=", "VES")], limit=1)
        )
        bs_currency.active = True
        self.env["res.currency.rate"].create(
            {
                "name": self.invoice.invoice_date,
                "currency_id": bs_currency.id,
                "rate": rate,
                "company_id": self.company.id,
            }
        )
        self.company.l10n_ve_bs_currency_id = bs_currency
        return bs_currency

    def test_vat_label_is_rif(self):
        self.assertEqual(self.env.ref("base.ve").vat_label, "RIF")

    def test_legal_datetime_without_hour(self):
        self.assertEqual(self.invoice._l10n_ve_legal_datetime(), "25-07-2026")

    def test_legal_datetime_with_known_hour(self):
        with patch.object(
            type(self.invoice),
            "_l10n_ve_emission_time",
            return_value="03.14.07 p.m",
        ):
            self.assertEqual(
                self.invoice._l10n_ve_legal_datetime(),
                "25-07-2026 03.14.07 p.m",
            )

    def test_exempt_predicate(self):
        lines = self.invoice.invoice_line_ids
        taxed = lines.filtered(lambda line: line.tax_ids == self.tax_16)
        exempt = lines.filtered(lambda line: line.tax_ids == self.tax_exempt)
        self.assertFalse(taxed._l10n_ve_is_exempt())
        self.assertTrue(exempt._l10n_ve_is_exempt())
        draft = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.invoice.partner_id.id,
                "invoice_line_ids": [
                    Command.create(
                        {
                            "name": "No Taxes",
                            "quantity": 1.0,
                            "price_unit": 10.0,
                            "tax_ids": [Command.clear()],
                        }
                    )
                ],
            }
        )
        self.assertTrue(draft.invoice_line_ids._l10n_ve_is_exempt())

    def test_report_renders_legal_marks(self):
        html = self._render_invoice()
        self.assertIn("(E)", html)
        self.assertIn("00-00001234", html)
        self.assertIn("Asignación del Nº de Control", html)
        self.assertIn("25-07-2026", html)

    def test_bs_amounts_use_document_date(self):
        self._setup_bs()
        amounts = self.invoice._l10n_ve_bs_amounts()
        self.assertEqual(amounts["rate"], 100.0)
        self.assertEqual(amounts["date"], self.invoice.invoice_date)
        self.assertEqual(amounts["untaxed"], self.invoice.amount_untaxed * 100)
        self.assertEqual(amounts["tax"], self.invoice.amount_tax * 100)
        self.assertEqual(amounts["total"], self.invoice.amount_total * 100)
        self.assertFalse(amounts["show_residual"])

    def test_bs_amounts_empty_without_currency(self):
        self.company.l10n_ve_bs_currency_id = False
        self.assertFalse(self.invoice._l10n_ve_bs_amounts())

    def test_bs_amounts_empty_when_document_already_in_bs(self):
        self.company.l10n_ve_bs_currency_id = self.invoice.currency_id
        self.assertFalse(self.invoice._l10n_ve_bs_amounts())

    def test_bs_amounts_empty_without_rate(self):
        bs_currency = (
            self.env["res.currency"]
            .with_context(active_test=False)
            .search([("name", "=", "VES")], limit=1)
        )
        bs_currency.rate_ids.unlink()
        self.company.l10n_ve_bs_currency_id = bs_currency
        self.assertFalse(self.invoice._l10n_ve_bs_amounts())

    def test_report_renders_bs_block_and_rate_note(self):
        self._setup_bs()
        html = self._render_invoice()
        self.assertIn("Total en Bs", html)
        self.assertIn("Monto sin impuestos en Bs", html)
        self.assertIn("Tasa de cambio aplicada", html)
        self.assertIn("25-07-2026", html)

    def test_report_line_tax_detail_toggle(self):
        self.assertTrue(self.company.l10n_ve_show_line_tax_detail)
        html = self._render_invoice()
        self.assertIn("Sin impuestos", html)
        self.assertIn("Impuesto", html)

        self.company.l10n_ve_show_line_tax_detail = False
        html = self._render_invoice()
        self.assertNotIn("Sin impuestos", html)

    def test_report_renders_printer_block(self):
        self.company.write(
            {
                "l10n_ve_printer_name": "Test Authorized Printer",
                "l10n_ve_printer_vat": "J-30000000-1",
                "l10n_ve_printer_auth_number": "SNAT/2024/0099",
                "l10n_ve_printer_auth_date": fields.Date.to_date("2025-01-15"),
            }
        )
        html = self._render_invoice()
        self.assertIn("Test Authorized Printer", html)
        self.assertIn("SNAT/2024/0099", html)
        self.assertIn("15-01-2025", html)

    def test_report_does_not_change_non_venezuelan_invoice(self):
        self._setup_bs()
        self.company.l10n_ve_printer_name = "Hidden Printer"
        self.company.account_fiscal_country_id = self.env.ref("base.us")
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.invoice.partner_id.id,
                "invoice_date": fields.Date.to_date("2026-07-25"),
                "l10n_ve_control_number": "00-00009999",
                "invoice_line_ids": [
                    Command.create(
                        {
                            "name": "Non-Venezuelan Product",
                            "quantity": 1.0,
                            "price_unit": 10.0,
                            "tax_ids": [Command.clear()],
                        }
                    )
                ],
            }
        )

        html = self._render_invoice(invoice)

        self.assertNotIn("Nº de Control", html)
        self.assertNotIn("(E)", html)
        self.assertNotIn("Sin impuestos", html)
        self.assertNotIn("Total en Bs", html)
        self.assertNotIn("Hidden Printer", html)
        self.assertFalse(invoice._l10n_ve_bs_amounts())
