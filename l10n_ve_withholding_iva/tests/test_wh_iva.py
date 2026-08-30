# Copyright 2026 BWEALTHICS LLC
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

import base64
from datetime import date
from unittest.mock import patch

from psycopg2 import IntegrityError

from odoo import Command
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import new_test_user, tagged
from odoo.tools import mute_logger

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged("post_install", "-at_install")
class TestL10nVeWhIva(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.company_data["company"]
        cls.change_company_country(cls.company, cls.env.ref("base.ve"))
        cls.company.vat = "J-12345678-4"
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
        cls.wh_journal = cls.company_data["default_journal_misc"]
        cls.company.l10n_ve_iva_wh_agent_account_id = cls.agent_account
        cls.company.l10n_ve_iva_wh_received_account_id = cls.received_account
        cls.company.l10n_ve_iva_wh_journal_id = cls.wh_journal
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
                "vat": "J-98765432-4",
                "l10n_ve_wh_iva_rate": "75",
                "l10n_ve_taxpayer_type": "especial",
            }
        )
        cls.customer = cls.env["res.partner"].create(
            {"name": "Cliente SPE VE", "email": "cliente@example.com"}
        )
        cls.eur = cls.setup_other_currency("EUR")
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
        currency=None,
        company_data=None,
        bill_date="2026-01-10",
    ):
        company_data = company_data or cls.company_data
        move = (
            cls.env["account.move"]
            .with_company(company_data["company"])
            .create(
                {
                    "move_type": move_type,
                    "partner_id": partner.id,
                    "invoice_date": bill_date,
                    "date": bill_date,
                    "ref": ref or False,
                    "currency_id": (currency or company_data["company"].currency_id).id,
                    "invoice_line_ids": [
                        Command.create(
                            {
                                "name": "Servicio de prueba",
                                "quantity": 1.0,
                                "price_unit": price_unit,
                                "tax_ids": [
                                    Command.set(
                                        company_data["default_tax_purchase"].ids
                                    )
                                ],
                            }
                        )
                    ],
                }
            )
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

    def _enable_spe(self, spe_date="2026-01-01", company=None):
        company = company or self.company
        company.l10n_ve_is_spe = True
        company.l10n_ve_spe_date = spe_date

    def _payable_lines(self, move):
        return move.line_ids.filtered(
            lambda line: line.account_id.account_type == "liability_payable"
        )

    def _assert_withholding(self, bill, rate):
        """Check voucher, entry and reconciliation of a withheld document."""
        voucher = bill.l10n_ve_iva_wh_voucher_id
        expected_wh = self.company.currency_id.round(bill.amount_tax * rate / 100.0)
        self.assertEqual(voucher.state, "posted")
        self.assertEqual(voucher.move_ids, bill)
        self.assertEqual(voucher.partner_id, bill.commercial_partner_id)
        self.assertEqual(voucher.date, bill.date)
        self.assertEqual(len(voucher.number), 14)
        self.assertTrue(voucher.number.startswith("202601"))
        self.assertEqual(voucher.wh_rate, rate)
        self.assertAlmostEqual(voucher.withheld_amount, expected_wh, places=2)
        self.assertAlmostEqual(voucher.tax_amount, bill.amount_tax, places=2)
        self.assertAlmostEqual(voucher.base_amount, bill.amount_untaxed, places=2)
        wh_move = voucher.wh_move_id
        self.assertEqual(wh_move.state, "posted")
        self.assertEqual(wh_move.journal_id, self.wh_journal)
        self.assertEqual(wh_move.date, bill.date)
        bill_payable = self._payable_lines(bill)
        wh_payable = wh_move.line_ids.filtered(
            lambda line: line.account_id == bill_payable.account_id
        )
        wh_agent = wh_move.line_ids.filtered(
            lambda line: line.account_id == self.agent_account
        )
        self.assertEqual(len(wh_move.line_ids), 2)
        self.assertAlmostEqual(wh_payable.balance, expected_wh, places=2)
        self.assertAlmostEqual(wh_agent.balance, -expected_wh, places=2)
        self.assertEqual(wh_payable.partner_id, bill.commercial_partner_id)
        self.assertTrue(wh_payable.reconciled)
        self.assertIn(
            bill_payable,
            wh_payable.matched_debit_ids.debit_move_id
            | wh_payable.matched_credit_ids.credit_move_id,
        )
        self.assertAlmostEqual(
            bill.amount_residual, bill.amount_total - expected_wh, places=2
        )
        self.assertAlmostEqual(
            voucher._l10n_ve_get_amount_for_move(bill), expected_wh, places=2
        )
        return voucher

    def test_post_bill_75_creates_voucher_and_reconciled_entry(self):
        self._enable_spe()
        bill = self._create_bill(self.vendor)
        self._assert_withholding(bill, 75.0)
        self.assertEqual(bill.payment_state, "partial")

    def test_post_bill_100(self):
        self._enable_spe()
        self.vendor.l10n_ve_wh_iva_rate = "100"
        bill = self._create_bill(self.vendor)
        self._assert_withholding(bill, 100.0)

    def test_post_bill_spe_supplier_is_withheld(self):
        self._enable_spe()
        bill = self._create_bill(self.vendor_spe)
        self._assert_withholding(bill, 75.0)

    def test_bill_before_spe_date_not_withheld(self):
        self._enable_spe(spe_date="2026-02-01")
        bill = self._create_bill(self.vendor)
        self.assertFalse(bill.l10n_ve_iva_wh_voucher_id)
        self.assertEqual(bill.amount_residual, bill.amount_total)

    def test_excluded_bill_not_withheld(self):
        self._enable_spe()
        bill = self._create_bill(self.vendor, post=False)
        bill.l10n_ve_iva_wh_excluded = True
        bill.action_post()
        self.assertFalse(bill.l10n_ve_iva_wh_voucher_id)
        with self.assertRaises(UserError):
            bill.action_l10n_ve_create_iva_wh()

    def test_company_not_spe_not_withheld(self):
        self.company.l10n_ve_is_spe = False
        bill = self._create_bill(self.vendor)
        self.assertFalse(bill.l10n_ve_iva_wh_voucher_id)
        self.assertEqual(bill.amount_residual, bill.amount_total)

    def test_non_ve_company_untouched(self):
        other_data = self.setup_other_company(name="Other Company")
        other_company = other_data["company"]
        self.assertNotEqual(other_company.account_fiscal_country_id.code, "VE")
        self._enable_spe(company=other_company)
        other_company.l10n_ve_iva_wh_journal_id = other_data["default_journal_misc"]
        bill = self._create_bill(self.vendor, company_data=other_data)
        self.assertFalse(bill.l10n_ve_iva_wh_voucher_id)
        self.assertEqual(bill.amount_residual, bill.amount_total)

    def test_partner_rate_zero_or_without_rif_not_withheld(self):
        self._enable_spe()
        self.vendor.l10n_ve_wh_iva_rate = "0"
        bill = self._create_bill(self.vendor)
        self.assertFalse(bill.l10n_ve_iva_wh_voucher_id)
        vendor = self.env["res.partner"].create({"name": "Proveedor sin RIF"})
        bill = self._create_bill(vendor)
        self.assertFalse(bill.l10n_ve_iva_wh_voucher_id)

    def test_foreign_currency_bill(self):
        self._enable_spe()
        bill = self._create_bill(self.vendor, currency=self.eur)
        voucher = bill.l10n_ve_iva_wh_voucher_id
        # 1000 EUR + 15% VAT at 2 EUR per company unit.
        tax_currency = bill.amount_tax
        tax_company = abs(bill.amount_tax_signed)
        self.assertAlmostEqual(tax_currency, 2.0 * tax_company, places=2)
        # Computed in company currency first, then converted at the bill rate.
        wh_company = self.company.currency_id.round(tax_company * 0.75)
        wh_currency = self.eur.round(wh_company * bill.invoice_currency_rate)
        self.assertAlmostEqual(voucher.withheld_amount, wh_company, places=2)
        bill_payable = self._payable_lines(bill)
        wh_payable = voucher.wh_move_id.line_ids.filtered(
            lambda line: line.account_id == bill_payable.account_id
        )
        self.assertEqual(wh_payable.currency_id, self.eur)
        self.assertAlmostEqual(wh_payable.amount_currency, wh_currency, places=2)
        self.assertAlmostEqual(wh_payable.balance, wh_company, places=2)
        self.assertTrue(wh_payable.reconciled)
        self.assertFalse(wh_payable.matched_credit_ids.exchange_move_id)
        self.assertAlmostEqual(
            bill.amount_residual, bill.amount_total - wh_currency, places=2
        )
        self.assertAlmostEqual(
            -bill.amount_residual_signed,
            -bill.amount_total_signed - wh_company,
            places=2,
        )

    def test_reset_to_draft_cancels_voucher_and_repost_issues_new(self):
        self._enable_spe()
        bill = self._create_bill(self.vendor)
        voucher = bill.l10n_ve_iva_wh_voucher_id
        number = voucher.number
        wh_move = voucher.wh_move_id
        with self.assertRaises(UserError):
            wh_move.button_draft()
        bill.button_draft()
        self.assertEqual(voucher.state, "cancel")
        self.assertEqual(voucher.number, number)
        self.assertEqual(wh_move.state, "cancel")
        self.assertFalse(bill.l10n_ve_iva_wh_voucher_id)
        self.assertFalse(self._payable_lines(bill).matched_debit_ids)
        bill.action_post()
        new_voucher = self._assert_withholding(bill, 75.0)
        self.assertNotEqual(new_voucher, voucher)
        self.assertEqual(int(new_voucher.number), int(number) + 1)

    def test_spoofed_voucher_pointer_does_not_cancel_other_voucher(self):
        self._enable_spe()
        bill = self._create_bill(self.vendor)
        other = self._create_bill(self.vendor)
        other_voucher = other.l10n_ve_iva_wh_voucher_id
        # The pointer is writable over RPC: it must not select the voucher.
        bill.l10n_ve_iva_wh_voucher_id = other_voucher
        bill.button_draft()
        self.assertEqual(other_voucher.state, "posted")
        self.assertEqual(other_voucher.wh_move_id.state, "posted")

    def test_cancel_bill_cancels_voucher(self):
        self._enable_spe()
        bill = self._create_bill(self.vendor)
        voucher = bill.l10n_ve_iva_wh_voucher_id
        bill.button_cancel()
        self.assertEqual(bill.state, "cancel")
        self.assertEqual(voucher.state, "cancel")
        self.assertEqual(voucher.wh_move_id.state, "cancel")

    def test_payment_after_posting_pays_net_only(self):
        self._enable_spe()
        bill = self._create_bill(self.vendor)
        net = bill.amount_residual
        wizard = self._register_wizard(bill)
        self.assertAlmostEqual(wizard.amount, net, places=2)
        action = wizard.action_create_payments()
        payment = self.env["account.payment"].browse(action["res_id"])
        self.assertAlmostEqual(payment.amount, net, places=2)
        self.assertEqual(bill.amount_residual, 0.0)
        self.assertFalse(
            payment.move_id.line_ids.filtered(
                lambda line: line.account_id == self.agent_account
            )
        )
        self.assertEqual(
            self.env["l10n.ve.iva.wh.voucher"].search_count(
                [("move_ids", "in", bill.ids)]
            ),
            1,
        )

    def test_multi_record_post(self):
        self._enable_spe()
        bill_1 = self._create_bill(self.vendor, post=False)
        bill_2 = self._create_bill(self.vendor_spe, price_unit=500.0, post=False)
        bill_3 = self._create_bill(self.vendor, price_unit=300.0, post=False)
        bill_3.l10n_ve_iva_wh_excluded = True
        (bill_1 + bill_2 + bill_3).action_post()
        self._assert_withholding(bill_1, 75.0)
        self._assert_withholding(bill_2, 75.0)
        self.assertFalse(bill_3.l10n_ve_iva_wh_voucher_id)
        self.assertNotEqual(
            bill_1.l10n_ve_iva_wh_voucher_id.number,
            bill_2.l10n_ve_iva_wh_voucher_id.number,
        )

    def test_missing_configuration_raises(self):
        self._enable_spe()
        self.company.l10n_ve_iva_wh_journal_id = False
        bill = self._create_bill(self.vendor, post=False)
        with self.assertRaises(UserError):
            bill.action_post()
        self.company.l10n_ve_iva_wh_journal_id = self.wh_journal
        self.company.l10n_ve_iva_wh_agent_account_id = False
        with self.assertRaises(UserError):
            bill.action_post()

    def test_button_withholds_bill_posted_before_configuration(self):
        bill = self._create_bill(self.vendor)
        self.assertFalse(bill.l10n_ve_iva_wh_voucher_id)
        self._enable_spe()
        bill.action_l10n_ve_create_iva_wh()
        self._assert_withholding(bill, 75.0)
        with self.assertRaises(UserError):
            bill.action_l10n_ve_create_iva_wh()

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
        self._create_bill(self.vendor)
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
        self.assertEqual(columns[0], "J123456784")
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
        self.assertAlmostEqual(
            bill.l10n_ve_iva_wh_voucher_id.withheld_amount, 150.0, places=2
        )
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
            float(by_rate["16.00"][10]), to_ves(120.0, date(2026, 1, 10)), places=2
        )
        self.assertAlmostEqual(
            float(by_rate["8.00"][10]), to_ves(30.0, date(2026, 1, 10)), places=2
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

    def _create_manual_voucher(self, **values):
        return self.env["l10n.ve.iva.wh.voucher"].create(
            {
                "date": "2026-01-15",
                "company_id": self.company.id,
                "partner_id": self.vendor.id,
                "withheld_amount": 10.0,
                **values,
            }
        )

    def test_voucher_invisible_to_other_company_user(self):
        self._enable_spe()
        bill = self._create_bill(self.vendor)
        voucher = bill.l10n_ve_iva_wh_voucher_id
        other_company = self.setup_other_company(name="Otra Compañía")["company"]
        user = new_test_user(
            self.env,
            login="wh_iva_other_company",
            groups="base.group_user,account.group_account_manager",
            company_id=other_company.id,
            company_ids=[Command.set(other_company.ids)],
        )
        voucher_model = self.env["l10n.ve.iva.wh.voucher"].with_user(user)
        self.assertFalse(voucher_model.search([("id", "=", voucher.id)]))
        with self.assertRaises(AccessError):
            voucher.with_user(user).read(["number"])
        export = (
            self.env["l10n.ve.iva.wh.txt.export"]
            .with_user(user)
            .create(
                {
                    "company_id": self.company.id,
                    "date_from": "2026-01-01",
                    "date_to": "2026-01-15",
                }
            )
        )
        with self.assertRaises(AccessError):
            export.action_generate()

    def test_invoicing_user_posts_bill_but_cannot_edit_voucher(self):
        self._enable_spe()
        user = new_test_user(
            self.env,
            login="wh_iva_invoicing",
            groups="base.group_user,account.group_account_invoice",
            company_id=self.company.id,
            company_ids=[Command.set(self.company.ids)],
        )
        bill = self._create_bill(self.vendor, post=False)
        bill.with_user(user).action_post()
        voucher = self._assert_withholding(bill, 75.0)
        user_voucher = voucher.with_user(user)
        self.assertEqual(user_voucher.read(["state"])[0]["state"], "posted")
        with self.assertRaises(AccessError):
            user_voucher.write({"exempt_amount": 1.0})
        with self.assertRaises(AccessError):
            user_voucher.action_cancel()
        # Resetting the bill still cancels the voucher it issued.
        bill.with_user(user).button_draft()
        self.assertEqual(voucher.state, "cancel")
        self.assertEqual(voucher.wh_move_id.state, "cancel")

    def test_posted_voucher_is_locked(self):
        self._enable_spe()
        voucher = self._create_bill(self.vendor).l10n_ve_iva_wh_voucher_id
        with self.assertRaises(UserError):
            voucher.write({"withheld_amount": 1.0})
        with self.assertRaises(UserError):
            voucher.write({"move_ids": [Command.clear()]})
        with self.assertRaises(UserError):
            voucher.write({"state": "draft"})
        with self.assertRaises(UserError):
            voucher.action_post()
        draft = self._create_manual_voucher()
        with self.assertRaises(UserError):
            draft.write({"state": "posted"})
        draft.write({"withheld_amount": 20.0})
        self.assertEqual(draft.withheld_amount, 20.0)
        # Neither in draft nor on create: state and links belong to the system.
        bill_move = self._create_bill(self.vendor)
        with self.assertRaises(UserError):
            draft.write({"wh_move_id": bill_move.id})
        with self.assertRaises(UserError):
            self.env["l10n.ve.iva.wh.voucher"].create(
                {
                    "date": "2026-01-15",
                    "company_id": self.company.id,
                    "partner_id": self.vendor.id,
                    "wh_rate": 75.0,
                    "state": "posted",
                }
            )
        with self.assertRaises(UserError):
            self.env["l10n.ve.iva.wh.voucher"].create(
                {
                    "date": "2026-01-15",
                    "company_id": self.company.id,
                    "partner_id": self.vendor.id,
                    "wh_rate": 75.0,
                    "wh_move_id": bill_move.id,
                }
            )

    def test_issued_manual_voucher_never_returns_to_draft(self):
        voucher = self._create_manual_voucher()
        voucher.action_post()
        number = voucher.number
        # No transition leads back to draft: cancelling is the only way out.
        self.assertFalse(hasattr(voucher, "action_draft"))
        with self.assertRaises(UserError):
            voucher.write({"state": "draft"})
        with self.assertRaises(UserError):
            voucher.action_post()
        with self.assertRaises(UserError):
            voucher.unlink()
        voucher.action_cancel()
        self.assertEqual(voucher.state, "cancel")
        self.assertEqual(voucher.number, number)
        with self.assertRaises(UserError):
            voucher.write({"state": "draft"})
        with self.assertRaises(UserError):
            voucher.action_cancel()
        with self.assertRaises(UserError):
            voucher.unlink()
        self.assertEqual(voucher.state, "cancel")
        self.assertEqual(voucher.number, number)
        # The replacement takes the next number of the sequence.
        replacement = self._create_manual_voucher()
        self.assertEqual(int(replacement.number), int(number) + 1)

    def test_voucher_number_only_from_sequence(self):
        for number in ("20260199999999", False):
            with self.subTest(number=number), self.assertRaises(UserError):
                self._create_manual_voucher(number=number)
        expected = self.env["l10n.ve.iva.wh.voucher"]._l10n_ve_next_voucher_number(
            "2026-01-15", company=self.company
        )
        draft = self._create_manual_voucher()
        self.assertEqual(int(draft.number), int(expected) + 1)
        for number in ("20260199999999", draft.number, False):
            with self.subTest(write=number), self.assertRaises(UserError):
                draft.write({"number": number})
        draft.action_post()
        with self.assertRaises(UserError):
            draft.write({"number": "20260199999999"})
        # Only drafts can be deleted.
        other = self._create_manual_voucher()
        other.unlink()
        self.assertFalse(other.exists())

    def test_wh_move_draft_ignores_old_context_key(self):
        self._enable_spe()
        voucher = self._create_bill(self.vendor).l10n_ve_iva_wh_voucher_id
        wh_move = voucher.wh_move_id
        with self.assertRaises(UserError):
            wh_move.with_context(l10n_ve_iva_wh_undo=True).button_draft()
        with self.assertRaises(UserError):
            wh_move.with_context(l10n_ve_iva_wh_undo=True).button_cancel()
        self.assertEqual(wh_move.state, "posted")
        self.assertEqual(voucher.state, "posted")

    def test_voucher_number_unique_per_company(self):
        voucher = self._create_manual_voucher()
        with mute_logger("odoo.sql_db"), self.assertRaises(IntegrityError):
            with self.env.cr.savepoint():
                self.env["l10n.ve.iva.wh.voucher"]._l10n_ve_create_unlocked(
                    [
                        {
                            "date": "2026-01-15",
                            "company_id": self.company.id,
                            "partner_id": self.vendor.id,
                            "number": voucher.number,
                        }
                    ]
                )
                self.env.flush_all()

    # ------------------------------------------------------------------
    # Vouchers issued outside the system
    # ------------------------------------------------------------------

    def _create_external_voucher(self, user=None, **values):
        model = self.env["l10n.ve.iva.wh.voucher"]
        if user:
            model = model.with_user(user)
        return model.create(
            {
                "date": "2026-01-15",
                "company_id": self.company.id,
                "partner_id": self.vendor.id,
                "withheld_amount": 10.0,
                "wh_rate": 75.0,
                "is_external": True,
                "number": "20260100000777",
                **values,
            }
        )

    def test_external_voucher_registered_and_issued_by_manager(self):
        accountant = self._accountant()
        before = self._create_manual_voucher()
        voucher = self._create_external_voucher(user=accountant)
        self.assertEqual(voucher.number, "20260100000777")
        self.assertTrue(voucher.is_external)
        # The number can be corrected while the voucher is a draft.
        voucher.write({"number": "20260100000778"})
        voucher.action_post()
        self.assertEqual(voucher.state, "posted")
        self.assertEqual(voucher.number, "20260100000778")
        # The external number did not consume the sequence.
        after = self._create_manual_voucher()
        self.assertEqual(int(after.number), int(before.number) + 1)
        # Once issued the number is locked like every fiscal field.
        for vals in (
            {"number": "20260100000779"},
            {"withheld_amount": 1.0},
            {"is_external": False},
            {"state": "draft"},
        ):
            with self.subTest(vals=vals), self.assertRaises(UserError):
                voucher.write(vals)
        voucher.action_cancel()
        with self.assertRaises(UserError):
            voucher.write({"number": "20260100000779"})
        self.assertEqual(voucher.number, "20260100000778")

    def test_external_voucher_number_format(self):
        accountant = self._accountant()
        for number in (
            "2026010000077",
            "202601000007777",
            "20261300000001",
            "20260000000001",
            "2026A100000001",
            "20260200000001",
        ):
            with self.subTest(number=number), self.assertRaises(ValidationError):
                self._create_external_voucher(user=accountant, number=number)
        for number in (False, ""):
            with self.subTest(number=number), self.assertRaises(UserError):
                self._create_external_voucher(user=accountant, number=number)
        voucher = self._create_external_voucher(user=accountant)
        with self.assertRaises(ValidationError):
            voucher.write({"number": "20261300000001"})

    def test_external_voucher_number_unique(self):
        accountant = self._accountant()
        existing = self._create_manual_voucher()
        with mute_logger("odoo.sql_db"), self.assertRaises(IntegrityError):
            with self.env.cr.savepoint():
                self._create_external_voucher(user=accountant, number=existing.number)
                self.env.flush_all()

    def test_external_voucher_requires_manager(self):
        user = new_test_user(
            self.env,
            login="wh_iva_external_invoicing",
            groups="base.group_user,account.group_account_invoice",
            company_id=self.company.id,
            company_ids=[Command.set(self.company.ids)],
        )
        with self.assertRaises(AccessError):
            self._create_external_voucher(user=user)
        # Even with create rights granted by another module, only the
        # accounting manager group may supply the number.
        self.env["ir.model.access"].create(
            {
                "name": "test create iva voucher",
                "model_id": self.env.ref(
                    "l10n_ve_withholding_iva.model_l10n_ve_iva_wh_voucher"
                ).id,
                "group_id": self.env.ref("account.group_account_invoice").id,
                "perm_read": True,
                "perm_write": True,
                "perm_create": True,
            }
        )
        with self.assertRaises(AccessError):
            self._create_external_voucher(user=user)
        draft = self._create_external_voucher(user=self._accountant())
        with self.assertRaises(AccessError):
            draft.with_user(user).write({"number": "20260100000778"})
        self.assertEqual(draft.number, "20260100000777")

    def test_automatic_voucher_number_stays_system_only(self):
        self._enable_spe()
        voucher = self._create_bill(self.vendor).l10n_ve_iva_wh_voucher_id
        self.assertFalse(voucher.is_external)
        self.assertRegex(voucher.number, r"^202601\d{8}$")
        accountant = self._accountant()
        for vals in ({"number": "20260100000777"}, {"is_external": True}):
            with self.subTest(vals=vals), self.assertRaises(UserError):
                voucher.with_user(accountant).write(vals)
        # A manual voucher not flagged as external keeps its sequence number.
        draft = self._create_manual_voucher()
        with self.assertRaises(UserError):
            draft.with_user(accountant).write({"number": "20260100000777"})

    # ------------------------------------------------------------------
    # Printed voucher (art. 16, PA SNAT/2025/000054)
    # ------------------------------------------------------------------

    def _render_voucher(self, voucher):
        html = self.env["ir.actions.report"]._render_qweb_html(
            "l10n_ve_withholding_iva.report_iva_wh_voucher", voucher.ids
        )[0]
        return " ".join(html.decode().split())

    def test_report_mandatory_content(self):
        self._enable_spe()
        self.vendor.email = "proveedor@example.com"
        voucher = self._create_bill(self.vendor).l10n_ve_iva_wh_voucher_id
        html = self._render_voucher(voucher)
        for text in (
            voucher.number,
            "Comprobante emitido conforme al artículo 16 de la Providencia "
            "Administrativa SNAT/2025/000054",
            "J-12345678-4",
            self.vendor.vat,
            "proveedor@example.com",
            "Fecha de Emisión",
            "Fecha de Entrega al Proveedor",
            "____/____/________",
            "Nº Control",
            "Base Imponible",
            "Monto Total",
            "% Retención",
            "75.00",
            voucher.fiscal_period,
        ):
            with self.subTest(text=text):
                self.assertIn(text, html)
        voucher.write({"delivery_date": "2026-01-20"})
        self.assertNotIn("____/____/________", self._render_voucher(voucher))

    def test_delivery_date_writable_after_issue(self):
        self._enable_spe()
        voucher = self._create_bill(self.vendor).l10n_ve_iva_wh_voucher_id
        accountant_voucher = voucher.with_user(self._accountant())
        accountant_voucher.write({"delivery_date": "2026-01-20"})
        self.assertEqual(voucher.delivery_date, date(2026, 1, 20))
        for vals in (
            {"delivery_date": "2026-01-21", "withheld_amount": 1.0},
            {"date": "2026-01-16"},
        ):
            with self.subTest(vals=vals), self.assertRaises(UserError):
                accountant_voucher.write(vals)
        self.assertEqual(voucher.delivery_date, date(2026, 1, 20))
        voucher.action_cancel()
        accountant_voucher.write({"delivery_date": False})
        self.assertFalse(voucher.delivery_date)

    def test_vendor_without_email_warns_but_does_not_block(self):
        self._enable_spe()
        self.assertFalse(self.vendor.email)
        bill = self._create_bill(self.vendor)
        voucher = bill.l10n_ve_iva_wh_voucher_id
        self.assertEqual(bill.state, "posted")
        self.assertEqual(voucher.state, "posted")
        self.assertTrue(voucher.partner_email_missing)
        self.vendor.email = "proveedor@example.com"
        voucher.invalidate_recordset(["partner_email_missing"])
        self.assertFalse(voucher.partner_email_missing)

    # ------------------------------------------------------------------
    # Purchase receipts
    # ------------------------------------------------------------------

    def test_purchase_receipt_not_withheld(self):
        self._enable_spe()
        receipt = self._create_bill(self.vendor, move_type="in_receipt")
        self.assertEqual(receipt.state, "posted")
        self.assertFalse(receipt.l10n_ve_iva_wh_voucher_id)
        self.assertFalse(
            self.env["l10n.ve.iva.wh.voucher"].search([("move_ids", "in", receipt.ids)])
        )
        self.assertEqual(receipt.amount_residual, receipt.amount_total)
        with self.assertRaises(UserError):
            receipt.action_l10n_ve_create_iva_wh()

    # ------------------------------------------------------------------
    # Vendor credit notes
    # ------------------------------------------------------------------

    def _create_refund(
        self, bill, price_unit, refund_date="2026-01-12", ref="NC-0001", post=True
    ):
        refund = self.env["account.move"].create(
            {
                "move_type": "in_refund",
                "partner_id": (bill.partner_id or self.vendor).id,
                "invoice_date": refund_date,
                "date": refund_date,
                "ref": ref,
                "currency_id": (bill.currency_id or self.company.currency_id).id,
                "reversed_entry_id": bill.id if bill else False,
                "invoice_line_ids": [
                    Command.create(
                        {
                            "name": "Devolución",
                            "quantity": 1.0,
                            "price_unit": price_unit,
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
        if post:
            refund.action_post()
        return refund

    def _export_txt(self, date_from="2026-01-01", date_to="2026-01-15"):
        export = self.env["l10n.ve.iva.wh.txt.export"].create(
            {
                "company_id": self.company.id,
                "date_from": date_from,
                "date_to": date_to,
            }
        )
        export.action_generate()
        content = base64.b64decode(export.file_data).decode()
        return [line.split("\t") for line in content.splitlines() if line]

    def _to_ves(self, amount, conversion_date):
        return self.company.currency_id._convert(
            amount, self.ves, self.company, conversion_date
        )

    def test_withholding_period_is_the_fortnight(self):
        voucher_model = self.env["l10n.ve.iva.wh.voucher"]
        self.assertEqual(
            voucher_model._l10n_ve_wh_period(date(2026, 2, 15)),
            (date(2026, 2, 1), date(2026, 2, 15)),
        )
        self.assertEqual(
            voucher_model._l10n_ve_wh_period(date(2026, 2, 16)),
            (date(2026, 2, 16), date(2026, 2, 28)),
        )
        self.assertTrue(
            voucher_model._l10n_ve_same_wh_period(date(2026, 1, 1), date(2026, 1, 15))
        )
        self.assertFalse(
            voucher_model._l10n_ve_same_wh_period(date(2026, 1, 15), date(2026, 1, 16))
        )

    def test_credit_note_of_other_vendor_leaves_voucher_untouched(self):
        """The reversal link is writable over RPC: a credit note of another
        vendor pointed at the bill must not cancel or adjust its voucher."""
        self._enable_spe()
        bill = self._create_bill(self.vendor)
        voucher = bill.l10n_ve_iva_wh_voucher_id
        self.assertEqual(voucher.state, "posted")
        amounts = (voucher.tax_amount, voucher.move_ids)
        refund = self._create_refund(bill, 100.0, post=False)
        refund.partner_id = self.vendor_spe
        refund.action_post()
        self.assertEqual(voucher.state, "posted")
        self.assertEqual((voucher.tax_amount, voucher.move_ids), amounts)
        self.assertNotIn(refund, voucher.move_ids)

    def test_partial_credit_note_same_period_adjusts_voucher(self):
        self._enable_spe()
        bill = self._create_bill(self.vendor, ref="FAC-00123")
        voucher = bill.l10n_ve_iva_wh_voucher_id
        refund = self._create_refund(bill, 200.0, ref="NC-00777")
        self.assertEqual(voucher.state, "posted")
        self.assertEqual(voucher.move_ids, bill | refund)
        self.assertEqual(refund.l10n_ve_iva_wh_voucher_id, voucher)
        # Net figures: 1000 - 200 base, 150 - 30 VAT, 112.50 - 22.50 withheld.
        self.assertAlmostEqual(voucher.base_amount, 800.0, places=2)
        self.assertAlmostEqual(voucher.tax_amount, 120.0, places=2)
        self.assertAlmostEqual(voucher.withheld_amount, 90.0, places=2)
        adjustment = voucher.adjustment_ids
        self.assertEqual(len(adjustment), 1)
        self.assertEqual(adjustment.refund_id, refund)
        self.assertAlmostEqual(adjustment.withheld_amount, 22.5, places=2)
        adjust_move = adjustment.move_id
        self.assertEqual(adjust_move.state, "posted")
        refund_payable = self._payable_lines(refund)
        adjust_payable = adjust_move.line_ids.filtered(
            lambda line: line.account_id == refund_payable.account_id
        )
        adjust_agent = adjust_move.line_ids.filtered(
            lambda line: line.account_id == self.agent_account
        )
        self.assertAlmostEqual(adjust_payable.balance, -22.5, places=2)
        self.assertAlmostEqual(adjust_agent.balance, 22.5, places=2)
        self.assertIn(
            refund_payable,
            adjust_payable.matched_debit_ids.debit_move_id,
        )
        # Net to pay: (1150 - 230) - 90 withheld.
        self.assertTrue(refund_payable.reconciled)
        self.assertAlmostEqual(bill.amount_residual, 830.0, places=2)
        agent_balance = sum(
            self.env["account.move.line"]
            .search(
                [
                    ("account_id", "=", self.agent_account.id),
                    ("parent_state", "=", "posted"),
                ]
            )
            .mapped("balance")
        )
        self.assertAlmostEqual(agent_balance, -90.0, places=2)
        # TXT: the bill as 01 and the credit note as 03, both positive.
        rows = self._export_txt()
        self.assertEqual(len(rows), 2)
        by_type = {row[4]: row for row in rows}
        self.assertEqual(set(by_type), {"01", "03"})
        refund_row = by_type["03"]
        self.assertEqual(refund_row[6], "NC-00777")
        self.assertEqual(refund_row[11], "FAC-00123")
        self.assertEqual(refund_row[12], voucher.number)
        self.assertEqual(by_type["01"][12], voucher.number)
        for row in rows:
            for index in (8, 9, 10, 13, 14):
                self.assertRegex(row[index], r"^\d+\.\d{2}$")
        self.assertAlmostEqual(
            float(refund_row[9]), self._to_ves(200.0, date(2026, 1, 12)), places=2
        )
        self.assertAlmostEqual(
            float(refund_row[10]), self._to_ves(22.5, voucher.date), places=2
        )
        self.assertAlmostEqual(
            float(by_type["01"][10]), self._to_ves(112.5, voucher.date), places=2
        )
        lines = voucher._l10n_ve_get_report_lines()
        self.assertTrue(
            all(
                line[key] >= 0
                for line in lines
                for key in ("total", "base", "tax", "withheld", "exempt")
            )
        )

    def test_partial_credit_note_reset_to_draft_restores_voucher(self):
        self._enable_spe()
        bill = self._create_bill(self.vendor)
        voucher = bill.l10n_ve_iva_wh_voucher_id
        refund = self._create_refund(bill, 200.0)
        adjust_move = voucher.adjustment_ids.move_id
        # The adjustment is protected while it belongs to the voucher.
        with self.assertRaises(UserError):
            adjust_move.button_draft()
        with self.assertRaises(UserError):
            self._payable_lines(refund).remove_move_reconcile()
        refund.button_draft()
        self.assertEqual(voucher.state, "posted")
        self.assertEqual(voucher.move_ids, bill)
        self.assertFalse(voucher.adjustment_ids)
        self.assertEqual(adjust_move.state, "cancel")
        self.assertFalse(refund.l10n_ve_iva_wh_voucher_id)
        self.assertAlmostEqual(voucher.base_amount, 1000.0, places=2)
        self.assertAlmostEqual(voucher.tax_amount, 150.0, places=2)
        self.assertAlmostEqual(voucher.withheld_amount, 112.5, places=2)
        self.assertEqual(voucher.wh_move_id.state, "posted")
        # Posting it again adds it back to the same voucher.
        refund.action_post()
        self.assertEqual(voucher.move_ids, bill | refund)
        self.assertAlmostEqual(voucher.withheld_amount, 90.0, places=2)
        self.assertEqual(len(voucher.adjustment_ids), 1)
        self.assertAlmostEqual(bill.amount_residual, 830.0, places=2)

    def test_partial_credit_note_by_invoicing_user(self):
        self._enable_spe()
        user = new_test_user(
            self.env,
            login="wh_iva_refund_invoicing",
            groups="base.group_user,account.group_account_invoice",
            company_id=self.company.id,
            company_ids=[Command.set(self.company.ids)],
        )
        bill = self._create_bill(self.vendor)
        voucher = bill.l10n_ve_iva_wh_voucher_id
        refund = self._create_refund(bill, 200.0, post=False)
        refund.with_user(user).action_post()
        self.assertEqual(voucher.move_ids, bill | refund)
        self.assertAlmostEqual(voucher.withheld_amount, 90.0, places=2)
        with self.assertRaises(AccessError):
            voucher.adjustment_ids.with_user(user).unlink()
        refund.with_user(user).button_draft()
        self.assertEqual(voucher.move_ids, bill)
        self.assertAlmostEqual(voucher.withheld_amount, 112.5, places=2)

    def test_total_credit_note_same_period_cancels_voucher(self):
        self._enable_spe()
        bill = self._create_bill(self.vendor)
        voucher = bill.l10n_ve_iva_wh_voucher_id
        wh_move = voucher.wh_move_id
        refund = self._create_refund(bill, 1000.0)
        self.assertEqual(voucher.state, "cancel")
        self.assertEqual(voucher.cancel_refund_id, refund)
        self.assertEqual(wh_move.state, "cancel")
        self.assertFalse(bill.l10n_ve_iva_wh_voucher_id)
        self.assertFalse(refund.l10n_ve_iva_wh_voucher_id)
        self.assertEqual(voucher.move_ids, bill)
        self.assertTrue(self._payable_lines(bill).reconciled)
        self.assertTrue(self._payable_lines(refund).reconciled)
        self.assertEqual(bill.amount_residual, 0.0)
        self.assertEqual(refund.amount_residual, 0.0)
        # Nothing is reported for the period.
        with self.assertRaises(UserError):
            self._export_txt()
        # The cancelled number cannot be revived by resetting the note.
        with self.assertRaises(UserError):
            refund.button_draft()
        with self.assertRaises(UserError):
            refund.button_cancel()
        self.assertEqual(refund.state, "posted")

    def test_partial_then_total_credit_note_cancels_voucher(self):
        self._enable_spe()
        bill = self._create_bill(self.vendor)
        voucher = bill.l10n_ve_iva_wh_voucher_id
        first = self._create_refund(bill, 200.0, ref="NC-1")
        adjust_move = voucher.adjustment_ids.move_id
        second = self._create_refund(bill, 800.0, ref="NC-2", refund_date="2026-01-14")
        self.assertEqual(voucher.state, "cancel")
        self.assertEqual(voucher.cancel_refund_id, second)
        self.assertEqual(voucher.wh_move_id.state, "cancel")
        self.assertEqual(adjust_move.state, "cancel")
        self.assertFalse(first.l10n_ve_iva_wh_voucher_id)
        self.assertEqual(bill.amount_residual, 0.0)
        # The first note no longer belongs to an issued voucher.
        first.button_draft()
        self.assertEqual(first.state, "draft")

    def test_total_credit_note_by_reversal_wizard(self):
        self._enable_spe()
        bill = self._create_bill(self.vendor)
        voucher = bill.l10n_ve_iva_wh_voucher_id
        wizard = (
            self.env["account.move.reversal"]
            .with_context(active_model="account.move", active_ids=bill.ids)
            .create(
                {
                    "date": "2026-01-14",
                    "journal_id": bill.journal_id.id,
                    "reason": "Anulación",
                }
            )
        )
        wizard.modify_moves()
        refund = bill.reversal_move_ids
        self.assertEqual(len(refund), 1)
        self.assertEqual(voucher.state, "cancel")
        self.assertEqual(voucher.cancel_refund_id, refund)
        self.assertEqual(voucher.wh_move_id.state, "cancel")
        self.assertEqual(bill.payment_state, "reversed")

    def test_reversal_with_cancel_of_earlier_period_is_refused(self):
        self._enable_spe()
        bill = self._create_bill(self.vendor)
        voucher = bill.l10n_ve_iva_wh_voucher_id
        wizard = (
            self.env["account.move.reversal"]
            .with_context(active_model="account.move", active_ids=bill.ids)
            .create(
                {
                    "date": "2026-01-20",
                    "journal_id": bill.journal_id.id,
                    "reason": "Anulación",
                }
            )
        )
        with self.assertRaises(UserError):
            wizard.modify_moves()
        self.assertEqual(voucher.state, "posted")

    def test_credit_note_later_period_not_withheld(self):
        self._enable_spe()
        bill = self._create_bill(self.vendor)
        voucher = bill.l10n_ve_iva_wh_voucher_id
        refund = self._create_refund(bill, 200.0, refund_date="2026-01-20")
        self.assertEqual(voucher.state, "posted")
        self.assertEqual(voucher.move_ids, bill)
        self.assertFalse(voucher.adjustment_ids)
        self.assertAlmostEqual(voucher.withheld_amount, 112.5, places=2)
        self.assertFalse(refund.l10n_ve_iva_wh_voucher_id)
        self.assertEqual(len(self._export_txt()), 1)
        with self.assertRaises(UserError):
            self._export_txt("2026-01-16", "2026-01-31")
        # A later total credit note leaves the voucher untouched too.
        total = self._create_refund(bill, 800.0, refund_date="2026-01-21")
        self.assertEqual(voucher.state, "posted")
        self.assertFalse(total.l10n_ve_iva_wh_voucher_id)
        refund.button_draft()
        self.assertEqual(voucher.state, "posted")

    def test_credit_note_without_bill_or_voucher_not_withheld(self):
        self._enable_spe()
        lone = self._create_refund(self.env["account.move"], 200.0)
        self.assertFalse(lone.reversed_entry_id)
        self.assertFalse(lone.l10n_ve_iva_wh_voucher_id)
        self.vendor.l10n_ve_wh_iva_rate = "0"
        bill = self._create_bill(self.vendor)
        self.assertFalse(bill.l10n_ve_iva_wh_voucher_id)
        self.vendor.l10n_ve_wh_iva_rate = "75"
        refund = self._create_refund(bill, 200.0)
        self.assertFalse(refund.l10n_ve_iva_wh_voucher_id)
        self.assertFalse(
            self.env["l10n.ve.iva.wh.voucher"].search(
                [("move_ids", "in", (lone | refund).ids)]
            )
        )
        with self.assertRaises(UserError):
            refund.action_l10n_ve_create_iva_wh()

    def test_bill_reset_cancels_voucher_with_credit_note_adjustments(self):
        self._enable_spe()
        bill = self._create_bill(self.vendor)
        voucher = bill.l10n_ve_iva_wh_voucher_id
        refund = self._create_refund(bill, 200.0)
        adjust_move = voucher.adjustment_ids.move_id
        bill.button_draft()
        self.assertEqual(voucher.state, "cancel")
        self.assertEqual(voucher.wh_move_id.state, "cancel")
        self.assertEqual(adjust_move.state, "cancel")
        self.assertFalse(refund.l10n_ve_iva_wh_voucher_id)

    # ------------------------------------------------------------------
    # Foreign currency rounding
    # ------------------------------------------------------------------

    def test_foreign_currency_withholding_ties_to_company_currency(self):
        self._enable_spe()
        # One foreign unit is worth 46.3842 company units (bolivars).
        usd = self.setup_other_currency(
            "CHF", rates=[("1900-01-01", 1.0 / 46.3842)], rounding=0.01
        )
        bill = self._create_bill(self.vendor, price_unit=1234.57, currency=usd)
        voucher = bill.l10n_ve_iva_wh_voucher_id
        company_currency = self.company.currency_id
        tax_lines = bill.line_ids.filtered("tax_line_id")
        product_lines = bill.invoice_line_ids
        tax_bs = sum(tax_lines.mapped("balance"))
        base_bs = sum(product_lines.mapped("balance"))
        self.assertTrue(company_currency.is_zero(voucher.tax_amount - tax_bs))
        self.assertTrue(company_currency.is_zero(voucher.base_amount - base_bs))
        expected_wh = company_currency.round(tax_bs * 0.75)
        self.assertTrue(company_currency.is_zero(voucher.withheld_amount - expected_wh))
        wh_payable = voucher.wh_move_id.line_ids.filtered(
            lambda line: line.account_id == self._payable_lines(bill).account_id
        )
        self.assertTrue(company_currency.is_zero(wh_payable.balance - expected_wh))
        self.assertTrue(
            usd.is_zero(
                wh_payable.amount_currency
                - usd.round(expected_wh * bill.invoice_currency_rate)
            )
        )
        # Paying the net settles the bill; any cent left in company currency
        # goes to the standard exchange difference entry.
        wizard = self._register_wizard(bill)
        self.assertEqual(wizard.currency_id, usd)
        self.assertAlmostEqual(wizard.amount, bill.amount_residual, places=2)
        wizard.action_create_payments()
        self.assertTrue(usd.is_zero(bill.amount_residual))
        self.assertTrue(company_currency.is_zero(bill.amount_residual_signed))
        self.assertIn(bill.payment_state, ("paid", "in_payment"))
        self.assertTrue(company_currency.is_zero(voucher.withheld_amount - expected_wh))
        self.assertTrue(company_currency.is_zero(wh_payable.balance - expected_wh))

    # ------------------------------------------------------------------
    # Hardening of the withholding entry
    # ------------------------------------------------------------------

    def _accountant(self):
        return new_test_user(
            self.env,
            login="wh_iva_accountant",
            groups="base.group_user,account.group_account_manager",
            company_id=self.company.id,
            company_ids=[Command.set(self.company.ids)],
        )

    def test_wh_move_cannot_be_undone_while_voucher_posted(self):
        self._enable_spe()
        bill = self._create_bill(self.vendor)
        voucher = bill.l10n_ve_iva_wh_voucher_id
        wh_move = voucher.wh_move_id.with_user(self._accountant())
        with self.assertRaises(UserError):
            wh_move.button_draft()
        with self.assertRaises(UserError):
            wh_move.button_cancel()
        with self.assertRaises(UserError):
            wh_move._reverse_moves([{"date": "2026-01-12"}])
        with self.assertRaises(UserError):
            wh_move._reverse_moves([{"date": "2026-01-12"}], cancel=True)
        with self.assertRaises(UserError):
            wh_move.unlink()
        self.assertEqual(wh_move.state, "posted")
        self.assertFalse(wh_move.reversal_move_ids)

    def test_wh_move_cannot_be_unreconciled_while_voucher_posted(self):
        self._enable_spe()
        bill = self._create_bill(self.vendor)
        voucher = bill.l10n_ve_iva_wh_voucher_id
        accountant = self._accountant()
        bill_payable = self._payable_lines(bill).with_user(accountant)
        partial = bill_payable.matched_debit_ids
        self.assertEqual(partial.debit_move_id.move_id, voucher.wh_move_id)
        with self.assertRaises(UserError):
            bill_payable.remove_move_reconcile()
        with self.assertRaises(UserError):
            bill.with_user(accountant).js_remove_outstanding_partial(partial.id)
        with self.assertRaises(UserError):
            partial.with_user(accountant).unlink()
        self.assertTrue(partial.exists())

    def test_voucher_cancel_still_undoes_wh_move(self):
        self._enable_spe()
        bill = self._create_bill(self.vendor)
        voucher = bill.l10n_ve_iva_wh_voucher_id.with_user(self._accountant())
        voucher.action_cancel()
        self.assertEqual(voucher.state, "cancel")
        self.assertEqual(voucher.wh_move_id.state, "cancel")
        self.assertFalse(self._payable_lines(bill).matched_debit_ids)
        self.assertEqual(bill.amount_residual, bill.amount_total)

    def test_ordinary_payment_can_be_unreconciled(self):
        self._enable_spe()
        bill = self._create_bill(self.vendor)
        voucher = bill.l10n_ve_iva_wh_voucher_id
        net = bill.amount_residual
        action = self._register_wizard(bill, amount=100.0).action_create_payments()
        payment = self.env["account.payment"].browse(action["res_id"])
        self.assertAlmostEqual(bill.amount_residual, net - 100.0, places=2)
        payment_lines = payment.move_id.line_ids.filtered(
            lambda line: line.account_id.account_type == "liability_payable"
        )
        payment_lines.with_user(self._accountant()).remove_move_reconcile()
        self.assertAlmostEqual(bill.amount_residual, net, places=2)
        self.assertEqual(voucher.state, "posted")
        self.assertTrue(
            voucher.wh_move_id.line_ids.filtered(
                lambda line: line.account_id.account_type == "liability_payable"
            ).reconciled
        )

    # ------------------------------------------------------------------
    # No negative amounts
    # ------------------------------------------------------------------

    def test_voucher_rejects_negative_amounts(self):
        with self.assertRaises(ValidationError):
            self._create_manual_voucher(withheld_amount=-10.0)
        voucher = self._create_manual_voucher()
        with self.assertRaises(ValidationError):
            voucher.write({"base_amount": -1.0})

    def test_txt_export_refuses_negative_rows(self):
        self._enable_spe()
        self._create_bill(self.vendor)
        voucher_class = type(self.env["l10n.ve.iva.wh.voucher"])
        original = voucher_class._l10n_ve_get_report_lines

        def negative_lines(voucher):
            lines = original(voucher)
            lines[0]["base"] = -lines[0]["base"]
            return lines

        with (
            patch.object(voucher_class, "_l10n_ve_get_report_lines", negative_lines),
            self.assertRaises(UserError),
        ):
            self._export_txt()
