# Copyright 2026 BWEALTHICS LLC
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

import base64
from datetime import date

from odoo import Command
from odoo.exceptions import ValidationError
from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged("post_install", "-at_install")
class TestL10nVeWhIva(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.company_data["company"]
        cls.company.vat = "J-12345678-9"
        cls.agent_account = cls.env["account.account"].create(
            {
                "name": "Retenciones de IVA por Enterar (test)",
                "code": "T210303",
                "account_type": "liability_current",
            }
        )
        cls.received_account = cls.env["account.account"].create(
            {
                "name": "Retenciones de IVA Recibidas de Clientes (test)",
                "code": "T110302",
                "account_type": "asset_current",
            }
        )
        cls.company.l10n_ve_iva_wh_agent_account_id = cls.agent_account
        cls.company.l10n_ve_iva_wh_received_account_id = cls.received_account
        cls.vendor = cls.env["res.partner"].create(
            {
                "name": "Proveedor Ordinario VE",
                "vat": "V-98765432-1",
                "l10n_ve_wh_iva_rate": "75",
            }
        )
        cls.vendor_spe = cls.env["res.partner"].create(
            {
                "name": "Proveedor SPE VE",
                "vat": "J-11122233-4",
                "l10n_ve_wh_iva_rate": "75",
                "l10n_ve_taxpayer_type": "especial",
            }
        )
        cls.customer = cls.env["res.partner"].create(
            {"name": "Cliente SPE VE", "vat": "J-55566677-8"}
        )
        ves = (
            cls.env["res.currency"]
            .with_context(active_test=False)
            .search([("name", "=", "VES")], limit=1)
        )
        if not ves:
            ves = cls.env["res.currency"].create(
                {"name": "VES", "symbol": "Bs.", "rounding": 0.01}
            )
        elif not ves.active:
            ves.active = True
        cls.ves = ves

    @classmethod
    def _create_bill(
        cls,
        partner,
        price_unit=1000.0,
        move_type="in_invoice",
        post=True,
        ref=False,
    ):
        move = cls.env["account.move"].create(
            {
                "move_type": move_type,
                "partner_id": partner.id,
                "invoice_date": "2026-01-10",
                "date": "2026-01-10",
                "ref": ref or False,
                "invoice_line_ids": [
                    Command.create(
                        {
                            "name": "Servicio de prueba",
                            "quantity": 1.0,
                            "price_unit": price_unit,
                            "tax_ids": [
                                Command.set(
                                    cls.company_data["default_tax_purchase"].ids
                                )
                            ],
                        }
                    )
                ],
            }
        )
        if post:
            move.action_post()
        return move

    @classmethod
    def _create_customer_invoice(cls, partner, price_unit=1000.0):
        move = cls.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": partner.id,
                "invoice_date": "2026-01-10",
                "date": "2026-01-10",
                "invoice_line_ids": [
                    Command.create(
                        {
                            "name": "Venta de prueba",
                            "quantity": 1.0,
                            "price_unit": price_unit,
                            "tax_ids": [
                                Command.set(cls.company_data["default_tax_sale"].ids)
                            ],
                        }
                    )
                ],
            }
        )
        move.action_post()
        return move

    def _register_wizard(self, moves, **values):
        return (
            self.env["account.payment.register"]
            .with_context(active_model="account.move", active_ids=moves.ids)
            .create({"payment_date": "2026-01-15", **values})
        )

    def _enable_spe(self, spe_date="2026-01-01"):
        self.company.l10n_ve_is_spe = True
        self.company.l10n_ve_spe_date = spe_date

    def _agent_writeoff_lines(self, payment):
        return payment.move_id.line_ids.filtered(
            lambda line: line.account_id == self.agent_account
        )

    def test_agent_disabled_no_withholding(self):
        self.company.l10n_ve_is_spe = False
        wizard = self._register_wizard(self._create_bill(self.vendor))
        self.assertEqual(wizard.l10n_ve_iva_wh_amount, 0.0)

    def test_agent_spe_date_in_future_no_withholding(self):
        self._enable_spe(spe_date="2030-01-01")
        wizard = self._register_wizard(self._create_bill(self.vendor))
        self.assertEqual(wizard.l10n_ve_iva_wh_amount, 0.0)

    def test_agent_supplier_spe_excluded(self):
        self._enable_spe()
        wizard = self._register_wizard(self._create_bill(self.vendor_spe))
        self.assertEqual(wizard.l10n_ve_iva_wh_amount, 0.0)

    def test_agent_partner_rate_zero_no_withholding(self):
        self._enable_spe()
        self.vendor.l10n_ve_wh_iva_rate = "0"
        wizard = self._register_wizard(self._create_bill(self.vendor))
        self.assertEqual(wizard.l10n_ve_iva_wh_amount, 0.0)

    def test_agent_no_rif_no_withholding(self):
        self._enable_spe()
        vendor = self.env["res.partner"].create({"name": "Proveedor sin RIF"})
        wizard = self._register_wizard(self._create_bill(vendor))
        self.assertEqual(wizard.l10n_ve_iva_wh_amount, 0.0)

    def test_agent_draft_invoice_no_withholding_flow_open(self):
        self._enable_spe()
        bill = self._create_bill(self.vendor, post=False)
        wizard = self._register_wizard(bill)
        self.assertEqual(wizard.l10n_ve_iva_wh_amount, 0.0)
        action = wizard.action_create_payments()
        payment = self.env["account.payment"].browse(action["res_id"])
        self.assertTrue(payment.exists())
        self.assertFalse(
            self.env["l10n.ve.iva.wh.voucher"].search([("move_ids", "in", bill.id)])
        )

    def test_agent_withholding_75_full_flow(self):
        self._enable_spe()
        bill = self._create_bill(self.vendor)
        expected_wh = self.company.currency_id.round(bill.amount_tax * 0.75)
        wizard = self._register_wizard(bill)
        self.assertAlmostEqual(wizard.l10n_ve_iva_wh_amount, expected_wh, places=2)
        action = wizard.action_create_payments()
        payment = self.env["account.payment"].browse(action["res_id"])
        self.assertAlmostEqual(
            payment.amount, bill.amount_total - expected_wh, places=2
        )
        self.assertEqual(bill.amount_residual, 0.0)
        writeoff_lines = self._agent_writeoff_lines(payment)
        self.assertEqual(len(writeoff_lines), 1)
        self.assertAlmostEqual(writeoff_lines.credit, expected_wh, places=2)
        voucher = self.env["l10n.ve.iva.wh.voucher"].search(
            [("payment_id", "=", payment.id)]
        )
        self.assertEqual(voucher.state, "posted")
        self.assertEqual(len(voucher.number), 14)
        self.assertTrue(voucher.number.startswith("202601"))
        self.assertAlmostEqual(voucher.withheld_amount, expected_wh, places=2)
        self.assertAlmostEqual(voucher.tax_amount, bill.amount_tax, places=2)
        self.assertAlmostEqual(voucher.base_amount, bill.amount_untaxed, places=2)
        self.assertEqual(voucher.wh_rate, 75.0)
        self.assertAlmostEqual(
            voucher._l10n_ve_get_amount_for_move(bill), expected_wh, places=2
        )
        other_move = self._create_bill(self.vendor, price_unit=50.0)
        self.assertEqual(voucher._l10n_ve_get_amount_for_move(other_move), 0.0)

    def test_agent_partial_payment_prorated(self):
        self._enable_spe()
        bill = self._create_bill(self.vendor)
        total = bill.amount_total
        expected_full_wh = self.company.currency_id.round(bill.amount_tax * 0.75)
        wizard = self._register_wizard(bill)
        wizard.amount = total / 2.0
        expected_wh = self.company.currency_id.round(expected_full_wh / 2.0)
        self.assertAlmostEqual(wizard.l10n_ve_iva_wh_amount, expected_wh, places=2)
        action = wizard.action_create_payments()
        payment = self.env["account.payment"].browse(action["res_id"])
        self.assertAlmostEqual(payment.amount, total / 2.0 - expected_wh, places=2)
        writeoff_lines = self._agent_writeoff_lines(payment)
        self.assertEqual(len(writeoff_lines), 1)
        self.assertAlmostEqual(writeoff_lines.credit, expected_wh, places=2)
        self.assertAlmostEqual(bill.amount_residual, total / 2.0, places=2)
        self.assertEqual(bill.payment_state, "partial")

    def test_agent_second_payment_not_rewithheld(self):
        self._enable_spe()
        bill = self._create_bill(self.vendor)
        total = bill.amount_total
        theoretical_wh = self.company.currency_id.round(bill.amount_tax * 0.75)
        wizard = self._register_wizard(bill)
        wizard.amount = total / 2.0
        first_wh = wizard.l10n_ve_iva_wh_amount
        wizard.action_create_payments()
        wizard2 = self._register_wizard(bill)
        expected_pending = theoretical_wh - first_wh
        self.assertAlmostEqual(
            wizard2.l10n_ve_iva_wh_amount, expected_pending, places=2
        )
        wizard2.action_create_payments()
        self.assertEqual(bill.amount_residual, 0.0)
        vouchers = self.env["l10n.ve.iva.wh.voucher"].search(
            [("move_ids", "in", bill.id)]
        )
        self.assertAlmostEqual(
            sum(vouchers.mapped("withheld_amount")), theoretical_wh, places=2
        )

    def test_received_withholding_flow(self):
        invoice = self._create_customer_invoice(self.customer)
        wh_received = self.company.currency_id.round(invoice.amount_tax * 0.75)
        wizard = self._register_wizard(
            invoice,
            l10n_ve_iva_wh_received_amount=wh_received,
            l10n_ve_iva_wh_voucher_number="20260100000001",
        )
        action = wizard.action_create_payments()
        payment = self.env["account.payment"].browse(action["res_id"])
        self.assertAlmostEqual(
            payment.amount, invoice.amount_total - wh_received, places=2
        )
        self.assertEqual(invoice.amount_residual, 0.0)
        writeoff_lines = payment.move_id.line_ids.filtered(
            lambda line: line.account_id == self.received_account
        )
        self.assertAlmostEqual(writeoff_lines.debit, wh_received, places=2)
        self.assertAlmostEqual(
            payment.l10n_ve_iva_wh_received_amount, wh_received, places=2
        )
        self.assertEqual(payment.l10n_ve_iva_wh_received_number, "20260100000001")

    def test_received_voucher_number_format(self):
        invoice = self._create_customer_invoice(self.customer)
        with self.assertRaises(ValidationError):
            self._register_wizard(
                invoice,
                l10n_ve_iva_wh_received_amount=10.0,
                l10n_ve_iva_wh_voucher_number="MAL-FORMATO-14",
            )

    def test_txt_export_16_columns(self):
        self._enable_spe()
        wizard = self._register_wizard(self._create_bill(self.vendor))
        wizard.action_create_payments()
        export = self.env["l10n.ve.iva.wh.txt.export"].create(
            {
                "company_id": self.company.id,
                "date_from": "2026-01-01",
                "date_to": "2026-01-15",
            }
        )
        export.action_generate()
        content = base64.b64decode(export.file_data).decode()
        lines = [line for line in content.splitlines() if line]
        self.assertEqual(len(lines), 1)
        columns = lines[0].split("\t")
        self.assertEqual(len(columns), 16)
        self.assertEqual(columns[0], "J123456789")
        self.assertEqual(columns[1], "202601")
        self.assertEqual(columns[2], "2026-01-10")
        self.assertEqual(columns[3], "C")
        self.assertEqual(columns[4], "01")
        self.assertEqual(columns[5], "V987654321")
        self.assertEqual(columns[7], "0")
        self.assertEqual(len(columns[12]), 14)
        self.assertEqual(columns[11], "0")
        self.assertEqual(columns[15], "0")
        for index in (8, 9, 10, 13, 14):
            self.assertRegex(columns[index], r"^\d+\.\d{2}$")

    def test_txt_export_multi_rate_one_line_per_rate(self):
        self._enable_spe()
        tax16 = self.env["account.tax"].create(
            {
                "name": "IVA 16% (Compras) test",
                "amount": 16.0,
                "amount_type": "percent",
                "type_tax_use": "purchase",
            }
        )
        tax8 = self.env["account.tax"].create(
            {
                "name": "IVA 8% (Compras) test",
                "amount": 8.0,
                "amount_type": "percent",
                "type_tax_use": "purchase",
            }
        )
        bill = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": self.vendor.id,
                "invoice_date": "2026-01-10",
                "date": "2026-01-10",
                "invoice_line_ids": [
                    Command.create(
                        {
                            "name": "Línea 16%",
                            "quantity": 1.0,
                            "price_unit": 1000.0,
                            "tax_ids": [Command.set(tax16.ids)],
                        }
                    ),
                    Command.create(
                        {
                            "name": "Línea 8%",
                            "quantity": 1.0,
                            "price_unit": 500.0,
                            "tax_ids": [Command.set(tax8.ids)],
                        }
                    ),
                ],
            }
        )
        bill.action_post()
        wizard = self._register_wizard(bill)
        self.assertAlmostEqual(wizard.l10n_ve_iva_wh_amount, 150.0, places=2)
        wizard.action_create_payments()
        export = self.env["l10n.ve.iva.wh.txt.export"].create(
            {
                "company_id": self.company.id,
                "date_from": "2026-01-01",
                "date_to": "2026-01-15",
            }
        )
        export.action_generate()
        lines = base64.b64decode(export.file_data).decode().splitlines()
        by_rate = {line.split("\t")[14]: line.split("\t") for line in lines if line}
        self.assertEqual(set(by_rate), {"8.00", "16.00"})

        def to_ves(amount, conversion_date):
            return self.company.currency_id._convert(
                amount, self.ves, self.company, conversion_date
            )

        self.assertAlmostEqual(
            float(by_rate["16.00"][9]), to_ves(1000.0, date(2026, 1, 10)), places=2
        )
        self.assertAlmostEqual(
            float(by_rate["8.00"][9]), to_ves(500.0, date(2026, 1, 10)), places=2
        )
        self.assertAlmostEqual(
            float(by_rate["16.00"][10]), to_ves(120.0, date(2026, 1, 15)), places=2
        )
        self.assertAlmostEqual(
            float(by_rate["8.00"][10]), to_ves(30.0, date(2026, 1, 15)), places=2
        )

    def test_report_lines_credit_note_affected_uses_ref(self):
        bill = self._create_bill(self.vendor, ref="FAC-00123")
        refund = self.env["account.move"].create(
            {
                "move_type": "in_refund",
                "partner_id": self.vendor.id,
                "invoice_date": "2026-01-12",
                "date": "2026-01-12",
                "ref": "NC-00777",
                "reversed_entry_id": bill.id,
                "invoice_line_ids": [
                    Command.create(
                        {
                            "name": "Devolución parcial",
                            "quantity": 1.0,
                            "price_unit": 100.0,
                            "tax_ids": [
                                Command.set(
                                    self.company_data["default_tax_purchase"].ids
                                )
                            ],
                        }
                    )
                ],
            }
        )
        refund.action_post()
        voucher = self.env["l10n.ve.iva.wh.voucher"].create(
            {
                "date": "2026-01-15",
                "company_id": self.company.id,
                "partner_id": self.vendor.id,
                "move_ids": [Command.set(refund.ids)],
                "withheld_amount": 0.0,
            }
        )
        line = voucher._l10n_ve_get_report_lines()[0]
        self.assertEqual(line["doc_type"], "03")
        self.assertEqual(line["doc_number"], "NC-00777")
        self.assertEqual(line["affected"], "FAC-00123")

    def test_voucher_sequence_monthly_reset_and_per_company(self):
        voucher_model = self.env["l10n.ve.iva.wh.voucher"]
        n1 = voucher_model._l10n_ve_next_voucher_number(
            "2026-03-05", company=self.company
        )
        n2 = voucher_model._l10n_ve_next_voucher_number(
            "2026-03-20", company=self.company
        )
        n3 = voucher_model._l10n_ve_next_voucher_number(
            "2026-04-02", company=self.company
        )
        self.assertEqual(n1, "20260300000001")
        self.assertEqual(n2, "20260300000002")
        self.assertEqual(n3, "20260400000001")
        other_company = self.env["res.company"].create({"name": "Otra Compañía VE"})
        m1 = voucher_model._l10n_ve_next_voucher_number(
            "2026-03-25", company=other_company
        )
        self.assertEqual(m1, "20260300000001")
        sequences = (
            self.env["ir.sequence"]
            .sudo()
            .search(
                [
                    ("code", "=", "l10n.ve.iva.wh.voucher"),
                    ("company_id", "in", [self.company.id, other_company.id]),
                ]
            )
        )
        self.assertEqual(
            set(sequences.mapped("company_id").ids),
            {self.company.id, other_company.id},
        )
        self.assertTrue(all(sequences.mapped("use_date_range")))
