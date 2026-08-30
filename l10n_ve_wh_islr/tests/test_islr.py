# Copyright 2026 BWEALTHICS LLC
# Part of l10n_ve_wh_islr. License LGPL-3.

import base64
import xml.etree.ElementTree as ET

from odoo import Command, fields
from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon

PAYMENT_DATE = "2026-07-15"


@tagged("post_install", "-at_install")
class TestIslrWithholding(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.company_data["company"]
        cls.company.with_context(no_vat_validation=True).vat = "J-12345678-9"
        cls.wh_account = cls.env["account.account"].create(
            {
                "code": "210401",
                "name": "Retenciones de ISLR por Enterar",
                "account_type": "liability_current",
            }
        )
        cls.company.l10n_ve_islr_wh_account_id = cls.wh_account
        cls.ves = cls.env["l10n.ve.ut"]._get_ves_currency()
        cls.ves.active = True
        cls.env["res.currency.rate"].create(
            {
                "currency_id": cls.ves.id,
                "name": "2026-01-01",
                "rate": 100.0,
                "company_id": cls.company.id,
            }
        )
        cls.ut_current = cls.env["l10n.ve.ut"].create(
            {
                "date_from": "2026-01-01",
                "value": 100.0,
                "gaceta": "G.O. de prueba",
            }
        )
        cls.concept = cls.env["l10n.ve.islr.concept"].create(
            {
                "name": "Honorarios de prueba",
                "seniat_code_pj": "004",
                "seniat_code_pn": "001",
                "rate_pj_dom": 5.0,
                "rate_pn_res": 3.0,
                "apply_subtrahend": True,
            }
        )
        cls.tax_iva16_purchase = cls.env["account.tax"].create(
            {
                "name": "IVA 16% (Compras) de prueba",
                "amount": 16.0,
                "amount_type": "percent",
                "type_tax_use": "purchase",
            }
        )
        partner_model = cls.env["res.partner"].with_context(no_vat_validation=True)
        cls.partner_pj = partner_model.create(
            {
                "name": "Proveedor PJ Domiciliada",
                "vat": "J-98765432-1",
                "l10n_ve_person_type": "pj_dom",
                "l10n_ve_islr_concept_id": cls.concept.id,
            }
        )
        cls.partner_pn = partner_model.create(
            {
                "name": "Proveedor PN Residente",
                "vat": "V-11222333-4",
                "l10n_ve_person_type": "pn_res",
                "l10n_ve_islr_concept_id": cls.concept.id,
            }
        )
        cls.partner_plain = partner_model.create(
            {
                "name": "Proveedor de Bienes",
                "vat": "J-55666777-8",
            }
        )

    def _create_bill(
        self,
        partner,
        amount,
        invoice_date=PAYMENT_DATE,
        taxes=None,
        ref="FAC-00012345",
    ):
        bill = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": partner.id,
                "invoice_date": invoice_date,
                "ref": ref,
                "invoice_line_ids": [
                    Command.create(
                        {
                            "name": "Servicio de prueba",
                            "quantity": 1.0,
                            "price_unit": amount,
                            "account_id": self.company_data[
                                "default_account_expense"
                            ].id,
                            "tax_ids": (
                                [Command.set(taxes.ids)] if taxes else [Command.clear()]
                            ),
                        }
                    )
                ],
            }
        )
        bill.action_post()
        return bill

    def _register_payment(self, bills, **extra_vals):
        wizard = (
            self.env["account.payment.register"]
            .with_context(active_model="account.move", active_ids=bills.ids)
            .create({"payment_date": PAYMENT_DATE, **extra_vals})
        )
        return wizard, wizard._create_payments()

    def _get_vouchers(self, payments):
        return self.env["l10n.ve.islr.voucher"].search(
            [("payment_id", "in", payments.ids)]
        )

    def _get_wh_lines(self, payments):
        return payments.move_id.line_ids.filtered(
            lambda line: line.account_id == self.wh_account
        )

    def test_ut_value_selection(self):
        ut_model = self.env["l10n.ve.ut"]
        ut_model.create({"date_from": "2026-08-01", "value": 200.0})
        self.assertEqual(
            ut_model.get_ut_value(fields.Date.to_date("2026-07-15")), 100.0
        )
        self.assertEqual(
            ut_model.get_ut_value(fields.Date.to_date("2026-08-02")), 200.0
        )
        with self.assertRaises(UserError):
            ut_model.get_ut_value(fields.Date.to_date("2000-01-01"))

    def test_pj_withholding_5pct(self):
        bill = self._create_bill(self.partner_pj, 1000.0)
        wizard, payments = self._register_payment(bill)
        self.assertEqual(len(payments), 1)
        self.assertAlmostEqual(payments.amount, 950.0, places=2)
        wh_lines = self._get_wh_lines(payments)
        self.assertTrue(wh_lines, "El pago debe tener línea de write-off en 210401")
        self.assertAlmostEqual(sum(wh_lines.mapped("credit")), 50.0, places=2)
        self.assertIn(bill.payment_state, ("paid", "in_payment"))
        self.assertAlmostEqual(wizard.amount, 1000.0, places=2)
        self.assertEqual(wizard.payment_difference_handling, "open")
        self.assertFalse(wizard.writeoff_account_id)
        voucher = self._get_vouchers(payments)
        self.assertEqual(len(voucher), 1)
        self.assertEqual(voucher.state, "issued")
        self.assertRegex(voucher.number, r"^202607\d{8}$")
        self.assertEqual(voucher.period, "202607")
        self.assertAlmostEqual(voucher.base, 1000.0, places=2)
        self.assertAlmostEqual(voucher.rate, 5.0, places=2)
        self.assertAlmostEqual(voucher.subtrahend, 0.0, places=2)
        self.assertAlmostEqual(voucher.amount, 50.0, places=2)
        self.assertIn(bill, voucher.move_ids)

    def test_pn_withholding_with_subtrahend(self):
        bill = self._create_bill(self.partner_pn, 1000.0)
        wizard, payments = self._register_payment(bill)
        self.assertAlmostEqual(wizard.l10n_ve_islr_subtrahend, 2.5, places=2)
        self.assertAlmostEqual(wizard.l10n_ve_islr_amount, 27.5, places=2)
        self.assertAlmostEqual(payments.amount, 972.5, places=2)
        voucher = self._get_vouchers(payments)
        self.assertEqual(len(voucher), 1)
        self.assertAlmostEqual(voucher.subtrahend, 2.5, places=2)
        self.assertAlmostEqual(voucher.amount, 27.5, places=2)
        self.assertEqual(voucher.person_type, "pn_res")

    def test_base_excludes_iva(self):
        bill = self._create_bill(self.partner_pj, 1000.0, taxes=self.tax_iva16_purchase)
        self.assertAlmostEqual(bill.amount_total, 1160.0, places=2)
        wizard, payments = self._register_payment(bill)
        self.assertAlmostEqual(wizard.amount, 1160.0, places=2)
        self.assertAlmostEqual(wizard.l10n_ve_islr_base, 1000.0, places=2)
        self.assertAlmostEqual(wizard.l10n_ve_islr_amount, 50.0, places=2)
        self.assertAlmostEqual(payments.amount, 1110.0, places=2)
        self.assertAlmostEqual(
            sum(self._get_wh_lines(payments).mapped("credit")), 50.0, places=2
        )
        self.assertIn(bill.payment_state, ("paid", "in_payment"))
        voucher = self._get_vouchers(payments)
        self.assertAlmostEqual(voucher.base, 1000.0, places=2)
        self.assertAlmostEqual(voucher.amount, 50.0, places=2)

    def test_partial_payment_prorated(self):
        bill = self._create_bill(self.partner_pj, 1000.0)
        wizard = (
            self.env["account.payment.register"]
            .with_context(active_model="account.move", active_ids=bill.ids)
            .create({"payment_date": PAYMENT_DATE})
        )
        wizard.amount = 400.0
        self.assertAlmostEqual(wizard.l10n_ve_islr_base, 400.0, places=2)
        self.assertAlmostEqual(wizard.l10n_ve_islr_amount, 20.0, places=2)
        payments = wizard._create_payments()
        self.assertAlmostEqual(payments.amount, 380.0, places=2)
        self.assertAlmostEqual(
            sum(self._get_wh_lines(payments).mapped("credit")), 20.0, places=2
        )
        self.assertEqual(bill.payment_state, "partial")
        self.assertAlmostEqual(bill.amount_residual, 600.0, places=2)
        voucher = self._get_vouchers(payments)
        self.assertEqual(len(voucher), 1)
        self.assertAlmostEqual(voucher.base, 400.0, places=2)
        self.assertAlmostEqual(voucher.amount, 20.0, places=2)

    def test_group_payment_voucher_per_invoice(self):
        bill_1 = self._create_bill(self.partner_pj, 600.0, ref="FAC-1111")
        bill_2 = self._create_bill(self.partner_pj, 400.0, ref="FAC-2222")
        _wizard, payments = self._register_payment(bill_1 + bill_2, group_payment=True)
        self.assertEqual(len(payments), 1)
        self.assertAlmostEqual(payments.amount, 950.0, places=2)
        self.assertAlmostEqual(
            sum(self._get_wh_lines(payments).mapped("credit")), 50.0, places=2
        )
        vouchers = self._get_vouchers(payments)
        self.assertEqual(len(vouchers), 2)
        by_bill = {voucher.move_ids: voucher for voucher in vouchers}
        self.assertEqual(set(by_bill), {bill_1, bill_2})
        self.assertAlmostEqual(by_bill[bill_1].base, 600.0, places=2)
        self.assertAlmostEqual(by_bill[bill_1].amount, 30.0, places=2)
        self.assertAlmostEqual(by_bill[bill_2].base, 400.0, places=2)
        self.assertAlmostEqual(by_bill[bill_2].amount, 20.0, places=2)
        self.assertAlmostEqual(sum(vouchers.mapped("amount")), 50.0, places=2)
        export = self.env["l10n.ve.islr.xml.export"].create(
            {"company_id": self.company.id, "year": "2026", "month": "07"}
        )
        export.action_generate()
        root = ET.fromstring(base64.b64decode(export.file_data))
        details = root.findall("DetalleRetencion")
        self.assertEqual(len(details), 2)
        numbers = {detail.findtext("NumeroFactura") for detail in details}
        self.assertEqual(numbers, {"1111", "2222"})
        amounts = {detail.findtext("MontoOperacion") for detail in details}
        self.assertEqual(amounts, {"60000.00", "40000.00"})

    def test_manual_amount_out_of_bounds(self):
        bill = self._create_bill(self.partner_pj, 1000.0)
        wizard = (
            self.env["account.payment.register"]
            .with_context(active_model="account.move", active_ids=bill.ids)
            .create({"payment_date": PAYMENT_DATE})
        )
        wizard.l10n_ve_islr_amount = 1500.0
        with self.assertRaises(UserError):
            wizard._create_payments()
        wizard.l10n_ve_islr_amount = -5.0
        with self.assertRaises(UserError):
            wizard._create_payments()
        wizard.l10n_ve_islr_amount = 10.0
        payments = wizard._create_payments()
        self.assertAlmostEqual(payments.amount, 990.0, places=2)
        self.assertAlmostEqual(self._get_vouchers(payments).amount, 10.0, places=2)

    def test_missing_ves_rate_blocks_subtrahend(self):
        self.env["res.currency.rate"].search(
            [("currency_id", "=", self.ves.id)]
        ).unlink()
        bill = self._create_bill(self.partner_pn, 1000.0)
        with self.assertRaises(UserError):
            self._register_payment(bill)

    def test_missing_ves_rate_blocks_xml_export(self):
        bill = self._create_bill(self.partner_pj, 1000.0)
        self._register_payment(bill)
        self.env["res.currency.rate"].search(
            [("currency_id", "=", self.ves.id)]
        ).unlink()
        export = self.env["l10n.ve.islr.xml.export"].create(
            {"company_id": self.company.id, "year": "2026", "month": "07"}
        )
        with self.assertRaises(UserError):
            export.action_generate()

    def test_placeholder_seniat_code_blocks_export(self):
        concept_000 = self.env["l10n.ve.islr.concept"].create(
            {
                "name": "Concepto sin código confirmado",
                "rate_pj_dom": 2.0,
            }
        )
        partner = (
            self.env["res.partner"]
            .with_context(no_vat_validation=True)
            .create(
                {
                    "name": "Proveedor Placeholder",
                    "vat": "J-44555666-7",
                    "l10n_ve_person_type": "pj_dom",
                    "l10n_ve_islr_concept_id": concept_000.id,
                }
            )
        )
        bill = self._create_bill(partner, 500.0)
        self._register_payment(bill)
        export = self.env["l10n.ve.islr.xml.export"].create(
            {"company_id": self.company.id, "year": "2026", "month": "07"}
        )
        with self.assertRaisesRegex(UserError, "anexo 6.1"):
            export.action_generate()

    def test_zero_declaration_when_no_vouchers(self):
        export = self.env["l10n.ve.islr.xml.export"].create(
            {"company_id": self.company.id, "year": "2026", "month": "02"}
        )
        export.action_generate()
        root = ET.fromstring(base64.b64decode(export.file_data))
        self.assertEqual(root.get("Periodo"), "202602")
        details = root.findall("DetalleRetencion")
        self.assertEqual(len(details), 1)
        detail = details[0]
        self.assertEqual(detail.findtext("CodigoConcepto"), "000")
        self.assertEqual(detail.findtext("RifRetenido"), "J123456789")
        self.assertEqual(detail.findtext("FechaOperacion"), "28/02/2026")
        self.assertEqual(detail.findtext("MontoOperacion"), "0.00")
        self.assertEqual(detail.findtext("PorcentajeRetencion"), "0.00")

    def test_no_concept_no_withholding_no_voucher(self):
        bill = self._create_bill(self.partner_plain, 500.0)
        _wizard, payments = self._register_payment(bill)
        self.assertAlmostEqual(payments.amount, 500.0, places=2)
        self.assertFalse(self._get_vouchers(payments))
        self.assertFalse(self._get_wh_lines(payments))

    def test_zero_withholding_still_creates_voucher(self):
        bill = self._create_bill(self.partner_pn, 50.0)
        _wizard, payments = self._register_payment(bill)
        self.assertAlmostEqual(payments.amount, 50.0, places=2)
        voucher = self._get_vouchers(payments)
        self.assertEqual(len(voucher), 1)
        self.assertEqual(voucher.state, "issued")
        self.assertAlmostEqual(voucher.amount, 0.0, places=2)

    def test_missing_account_raises(self):
        self.company.l10n_ve_islr_wh_account_id = False
        bill = self._create_bill(self.partner_pj, 100.0)
        wizard = (
            self.env["account.payment.register"]
            .with_context(active_model="account.move", active_ids=bill.ids)
            .create({"payment_date": PAYMENT_DATE})
        )
        with self.assertRaises(UserError):
            wizard._create_payments()

    def test_sequence_per_company_monthly_reset(self):
        bill_july = self._create_bill(self.partner_pj, 100.0)
        _wizard, payments_july = self._register_payment(bill_july)
        voucher_july = self._get_vouchers(payments_july)
        self.assertEqual(voucher_july.number, "20260700000001")
        sequence = (
            self.env["ir.sequence"]
            .sudo()
            .search(
                [
                    ("code", "=", "l10n.ve.islr.voucher"),
                    ("company_id", "=", self.company.id),
                ]
            )
        )
        self.assertEqual(len(sequence), 1)
        self.assertTrue(sequence.use_date_range)
        bill_august = self._create_bill(self.partner_pj, 100.0)
        _wizard, payments_august = self._register_payment(
            bill_august, payment_date="2026-08-05"
        )
        voucher_august = self._get_vouchers(payments_august)
        self.assertEqual(voucher_august.number, "20260800000001")
        self.assertEqual(voucher_august.period, "202608")

    def test_xml_export(self):
        bill_pj = self._create_bill(self.partner_pj, 1000.0)
        self._register_payment(bill_pj)
        bill_pn = self._create_bill(self.partner_pn, 50.0)
        self._register_payment(bill_pn)

        export = self.env["l10n.ve.islr.xml.export"].create(
            {
                "company_id": self.company.id,
                "year": "2026",
                "month": "07",
            }
        )
        export.action_generate()
        self.assertTrue(export.file_data)
        self.assertEqual(
            export.file_name, "RelacionRetencionesISLR_J123456789_202607.xml"
        )

        data = base64.b64decode(export.file_data)
        self.assertIn(b"ISO-8859-1", data[:80])
        root = ET.fromstring(data)
        self.assertEqual(root.tag, "RelacionRetencionesISLR")
        self.assertEqual(root.get("Periodo"), "202607")
        self.assertRegex(root.get("RifAgente"), r"^[VEJPG]\d{9}$")

        details = root.findall("DetalleRetencion")
        self.assertEqual(len(details), 2)
        rates = [detail.findtext("PorcentajeRetencion") for detail in details]
        self.assertIn("5.00", rates)
        self.assertIn("0.00", rates)
        for detail in details:
            self.assertRegex(detail.findtext("RifRetenido"), r"^[VEJPG]\d{9}$")
            self.assertRegex(detail.findtext("FechaOperacion"), r"^\d{2}/\d{2}/\d{4}$")
            self.assertRegex(detail.findtext("CodigoConcepto"), r"^\d{3}$")
            self.assertRegex(detail.findtext("MontoOperacion"), r"^\d+\.\d{2}$")
            self.assertRegex(detail.findtext("NumeroFactura"), r"^\d{1,10}$")
            self.assertTrue(detail.findtext("NumeroControl"))
        amounts = [detail.findtext("MontoOperacion") for detail in details]
        self.assertIn("100000.00", amounts)
