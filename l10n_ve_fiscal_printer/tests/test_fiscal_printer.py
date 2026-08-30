# Copyright 2026 BWEALTHICS LLC
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import Command, fields
from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged("post_install", "-at_install")
class TestFiscalPrinter(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company.country_id = cls.env.ref("base.ve")
        cls.company.account_fiscal_country_id = cls.env.ref("base.ve")
        cls.today = fields.Date.today()
        cls.sale_journal = cls.company_data["default_journal_sale"]
        cls.sale_journal.l10n_ve_emission_medium = "fiscal_machine"
        cls.ves = (
            cls.env["res.currency"]
            .with_context(active_test=False)
            .search([("name", "=", "VES")], limit=1)
        )
        cls.ves.active = True
        if not cls.ves.rate_ids.filtered(lambda rate: rate.name == cls.today):
            cls.env["res.currency.rate"].create(
                {
                    "currency_id": cls.ves.id,
                    "name": cls.today,
                    "company_id": cls.company.id,
                    "rate": 732.48,
                }
            )
        cls.config = (
            cls.env["pos.config"]
            .sudo()
            .create(
                {
                    "name": "Fiscal Printer Test POS",
                    "invoice_journal_id": cls.sale_journal.id,
                    "l10n_ve_bridge_url": "http://localhost:5001",
                    "l10n_ve_bridge_token": "test-token",
                    "l10n_ve_machine_serial": "TEST123456",
                }
            )
        )
        tax_group = cls.env["account.tax.group"].create(
            {
                "name": "Test VAT",
                "company_id": cls.company.id,
                "country_id": cls.env.ref("base.ve").id,
            }
        )
        cls.tax_16 = cls.env["account.tax"].create(
            {
                "name": "Test VAT 16%",
                "amount": 16.0,
                "type_tax_use": "sale",
                "company_id": cls.company.id,
                "country_id": cls.env.ref("base.ve").id,
                "tax_group_id": tax_group.id,
            }
        )
        cls.partner = cls.env["res.partner"].create(
            {"name": "Fiscal Test Customer", "vat": "J-12345678-9"}
        )
        cls.product = cls.env["product.product"].create(
            {
                "name": "A fiscal test product with more than forty characters",
                "list_price": 10.0,
            }
        )

    def _invoice(self, move_type="out_invoice", lines=None, **extra):
        lines = lines or [
            Command.create(
                {
                    "product_id": self.product.id,
                    "quantity": 2,
                    "price_unit": 10.0,
                    "tax_ids": [Command.set(self.tax_16.ids)],
                }
            ),
            Command.create(
                {
                    "product_id": self.product.id,
                    "quantity": 1,
                    "price_unit": 5.0,
                    "tax_ids": [Command.clear()],
                }
            ),
        ]
        move = self.env["account.move"].create(
            {
                "move_type": move_type,
                "partner_id": self.partner.id,
                "journal_id": self.sale_journal.id,
                "invoice_date": self.today,
                "invoice_line_ids": lines,
                **extra,
            }
        )
        move.action_post()
        return move

    def _session(self):
        return (
            self.env["pos.session"]
            .sudo()
            .create({"config_id": self.config.id, "user_id": self.env.uid})
        )

    def _pos_order(self, session, **extra):
        values = {
            "session_id": session.id,
            "company_id": self.company.id,
            "partner_id": self.partner.id,
            "amount_tax": 1.6,
            "amount_total": 11.6,
            "amount_paid": 11.6,
            "amount_return": 0.0,
            "lines": [
                Command.create(
                    {
                        "product_id": self.product.id,
                        "qty": 1.0,
                        "price_unit": 10.0,
                        "price_subtotal": 10.0,
                        "price_subtotal_incl": 11.6,
                        "tax_ids": [Command.set(self.tax_16.ids)],
                    }
                )
            ],
        }
        values.update(extra)
        return self.env["pos.order"].sudo().create(values)

    def test_pos_data_fields_and_optional_igtf_default(self):
        payment_fields = self.env["pos.payment.method"]._load_pos_data_fields(
            self.config
        )
        self.assertIn("l10n_ve_fiscal_payment_code", payment_fields)
        self.assertIn("l10n_ve_igtf_applies", payment_fields)
        payment_method = (
            self.env["pos.payment.method"]
            .sudo()
            .create({"name": "Fiscal payment", "company_id": self.company.id})
        )
        self.assertFalse(payment_method.l10n_ve_igtf_applies)

    def test_ves_rate(self):
        expected = self.company.currency_id._convert(
            1.0, self.ves, self.company, self.today, round=False
        )
        self.assertAlmostEqual(self.config.l10n_ve_get_ves_rate(), expected, places=4)

    def test_missing_ves_rate_blocks_payload(self):
        self.env["res.currency.rate"].search(
            [("currency_id", "=", self.ves.id)]
        ).unlink()
        self.assertEqual(self.config.l10n_ve_get_ves_rate(), 0.0)
        with self.assertRaises(UserError):
            self._invoice()._l10n_ve_build_payload(self.config)

    def test_nearest_supported_tax_rate(self):
        moves = self.env["account.move"]
        self.assertEqual(moves._l10n_ve_rate_pct(self.tax_16), 16)
        self.assertEqual(moves._l10n_ve_rate_pct(self.env["account.tax"]), 0)

    def test_backend_invoice_payload(self):
        move = self._invoice()
        payload = move._l10n_ve_build_payload(self.config)
        self.assertEqual(payload["cliente_rif"], "J123456789")
        self.assertEqual(payload["serial_impresora"], "TEST123456")
        self.assertEqual(len(payload["items"]), 2)
        self.assertEqual(payload["items"][0]["iva_porcentaje"], 16)
        self.assertEqual(payload["items"][1]["iva_porcentaje"], 0)
        self.assertLessEqual(len(payload["items"][0]["descripcion"]), 40)
        machine_total = round(
            sum(item["precio"] * item["cantidad"] for item in payload["items"]),
            2,
        )
        self.assertEqual(payload["monto_total"], machine_total)
        self.assertEqual(payload["pagos"], [{"metodo": "01", "monto": machine_total}])

    def test_negative_backend_line_is_blocked(self):
        move = self._invoice(
            lines=[
                Command.create(
                    {
                        "product_id": self.product.id,
                        "quantity": 1,
                        "price_unit": 10.0,
                        "tax_ids": [Command.clear()],
                    }
                ),
                Command.create(
                    {
                        "product_id": self.product.id,
                        "quantity": 1,
                        "price_unit": -3.0,
                        "tax_ids": [Command.clear()],
                    }
                ),
            ]
        )
        with self.assertRaises(UserError):
            move._l10n_ve_build_payload(self.config)

    def test_multiple_bridge_configs_are_blocked(self):
        self.env["pos.config"].sudo().create(
            {
                "name": "Second Fiscal POS",
                "l10n_ve_bridge_url": "http://localhost:5001",
            }
        )
        with self.assertRaises(UserError):
            self._invoice()._l10n_ve_get_bridge_config()

    def test_credit_note_payload_requires_and_references_origin(self):
        origin = self._invoice()
        refund = self._invoice(move_type="out_refund", reversed_entry_id=origin.id)
        with self.assertRaises(UserError):
            refund._l10n_ve_build_payload(self.config)
        origin.l10n_ve_set_fiscal_result("00001325", "TEST123456", "invoice")
        payload = refund._l10n_ve_build_payload(self.config)
        self.assertEqual(payload["numero_factura_afectada"], "00001325")
        self.assertEqual(payload["serial_afectada"], "TEST123456")
        self.assertEqual(payload["fecha_afectada"], self.today.strftime("%d%m%Y"))

    def test_fiscal_result_uses_safe_control_assignment(self):
        move = self._invoice()
        move.l10n_ve_set_fiscal_result("00001326", "TEST123456", "invoice")
        self.assertEqual(move.l10n_ve_fiscal_number, "00001326")
        self.assertEqual(move.l10n_ve_control_number, "00001326")
        self.assertEqual(move.l10n_ve_control_date, self.today)
        self.assertEqual(move.l10n_ve_fiscal_doc_type, "invoice")
        self.assertTrue(move.l10n_ve_fiscal_date)
        move.l10n_ve_set_fiscal_result("00001326", "TEST123456", "invoice")
        with self.assertRaises(UserError):
            move.l10n_ve_set_fiscal_result("00001399", "TEST123456", "invoice")
        self.assertEqual(move.l10n_ve_control_number, "00001326")

    def test_backend_action(self):
        move = self._invoice()
        action = move.action_l10n_ve_print_fiscal()
        self.assertEqual(action["tag"], "l10n_ve_fiscal_printer.print_fiscal")
        self.assertEqual(action["params"]["endpoint"], "/print-invoice")
        self.assertEqual(action["params"]["bridge_url"], "http://localhost:5001")
        self.assertEqual(action["params"]["payload"]["uuid"], f"move-{move.id}")
        move.l10n_ve_set_fiscal_result("00000001", "TEST123456", "invoice")
        with self.assertRaises(UserError):
            move.action_l10n_ve_print_fiscal()

    def test_backend_action_requires_fiscal_machine_medium(self):
        self.sale_journal.l10n_ve_emission_medium = "free"
        move = self._invoice()
        with self.assertRaises(UserError):
            move.action_l10n_ve_print_fiscal()

    def test_pos_invoice_propagates_result_through_safe_api(self):
        order = self._pos_order(
            self._session(),
            l10n_ve_fiscal_number="00001327",
            l10n_ve_fiscal_machine_serial="TEST123456",
            l10n_ve_fiscal_date="2026-08-30 10:00:00",
            l10n_ve_fiscal_doc_type="invoice",
        )
        values = order._prepare_invoice_vals()
        self.assertNotIn("l10n_ve_control_number", values)
        invoice = order._create_invoice(values)
        invoice._post(soft=False)
        self.assertEqual(invoice.l10n_ve_control_number, "00001327")
        self.assertEqual(invoice.l10n_ve_control_date.isoformat(), "2026-08-30")
        self.assertEqual(invoice.l10n_ve_fiscal_number, "00001327")
        self.assertEqual(invoice.l10n_ve_fiscal_machine_serial, "TEST123456")

    def test_consolidated_invoice_with_fiscal_order_is_blocked(self):
        session = self._session()
        plain_order = self._pos_order(session)
        fiscal_order = self._pos_order(session, l10n_ve_fiscal_number="00001111")
        with self.assertRaises(UserError):
            (plain_order | fiscal_order)._prepare_invoice_vals()

    def test_z_report_number_is_stored_on_session(self):
        session = self._session()
        session.l10n_ve_z_number = "Z-00042"
        self.assertEqual(session.l10n_ve_z_number, "Z-00042")
