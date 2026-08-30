# Copyright 2026 BWEALTHICS LLC
# Part of l10n_ve_withholding_islr. License LGPL-3.

import base64
import xml.etree.ElementTree as ET

from odoo import Command, fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import new_test_user, tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon

from ..models.res_partner import is_valid_rif

BILL_DATE = "2026-07-15"


@tagged("post_install", "-at_install")
class TestIslrWithholding(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.company_data["company"]
        cls.change_company_country(cls.company, cls.env.ref("base.ve"))
        cls.company.with_context(no_vat_validation=True).vat = "J-12345678-4"
        cls.wh_account = cls.env["account.account"].create(
            {
                "code": "210401",
                "name": "Retenciones de ISLR por Enterar",
                "account_type": "liability_current",
            }
        )
        cls.wh_journal = cls.company_data["default_journal_misc"]
        cls.company.l10n_ve_islr_wh_account_id = cls.wh_account
        cls.company.l10n_ve_islr_wh_journal_id = cls.wh_journal
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
                "seniat_code_pn": "002",
                "rate_pj_dom": 5.0,
                "rate_pn_res": 3.0,
                "seniat_code_pn_nores": "003",
                "rate_pn_nores": 34.0,
                "base_pct_pn_nores": 90.0,
                "seniat_code_pj_nodom": "005",
                "pj_nodom_rate_type": "tarifa2",
                "base_pct_pj_nodom": 90.0,
                "apply_subtrahend": True,
            }
        )
        cls.concept_t2 = cls.env["l10n.ve.islr.concept"].create(
            {
                "name": "Asistencia técnica de prueba",
                "seniat_code_pn_nores": "036",
                "rate_pn_nores": 34.0,
                "base_pct_pn_nores": 30.0,
                "seniat_code_pj_nodom": "037",
                "pj_nodom_rate_type": "tarifa2",
                "base_pct_pj_nodom": 30.0,
            }
        )
        cls.concept_2 = cls.env["l10n.ve.islr.concept"].create(
            {
                "name": "Fletes de prueba",
                "seniat_code_pj": "072",
                "seniat_code_pn": "071",
                "rate_pj_dom": 3.0,
                "rate_pn_res": 1.0,
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
                "vat": "J-98765432-4",
                "email": "pj@example.com",
                "l10n_ve_person_type": "pj_dom",
                "l10n_ve_islr_concept_id": cls.concept.id,
            }
        )
        cls.partner_pn = partner_model.create(
            {
                "name": "Proveedor PN Residente",
                "vat": "V-98765432-1",
                "email": "pn@example.com",
                "l10n_ve_person_type": "pn_res",
                "l10n_ve_islr_concept_id": cls.concept.id,
            }
        )
        # Fictitious RIF whose check digit comes from the module helper.
        cls.partner_foreign = partner_model.create(
            {
                "name": "Proveedor PJ No Domiciliada",
                "vat": "J-45678901-2",
                "email": "foreign@example.com",
                "l10n_ve_person_type": "pj_nodom",
                "l10n_ve_islr_concept_id": cls.concept_t2.id,
            }
        )
        cls.partner_plain = partner_model.create(
            {
                "name": "Proveedor de Bienes",
                "vat": "J-98765432-4",
                "email": "bienes@example.com",
            }
        )
        cls.product_freight = cls.env["product.product"].create(
            {
                "name": "Servicio de flete",
                "type": "service",
                "l10n_ve_islr_concept_id": cls.concept_2.id,
            }
        )
        cls.eur = cls.setup_other_currency("EUR")

    @classmethod
    def _create_bill(
        cls,
        partner,
        amount=1000.0,
        bill_date=BILL_DATE,
        taxes=None,
        ref="FAC-00012345",
        move_type="in_invoice",
        currency=None,
        lines=None,
        post=True,
        company_data=None,
        user=None,
        reversed_entry=None,
    ):
        company_data = company_data or cls.company_data
        if lines is None:
            lines = [{"price_unit": amount}]
        line_cmds = []
        for line in lines:
            vals = {
                "name": "Servicio de prueba",
                "quantity": 1.0,
                "account_id": company_data["default_account_expense"].id,
                "tax_ids": ([Command.set(taxes.ids)] if taxes else [Command.clear()]),
            }
            vals.update(line)
            line_cmds.append(Command.create(vals))
        move_model = cls.env["account.move"].with_company(company_data["company"])
        if user:
            move_model = move_model.with_user(user)
        bill = move_model.create(
            {
                "move_type": move_type,
                "partner_id": partner.id,
                "invoice_date": bill_date,
                "date": bill_date,
                "ref": ref,
                "currency_id": (currency or company_data["company"].currency_id).id,
                "invoice_line_ids": line_cmds,
                "reversed_entry_id": reversed_entry.id if reversed_entry else False,
            }
        )
        if post:
            bill.action_post()
        return bill

    def _payable_lines(self, move):
        return move.line_ids.filtered(
            lambda line: line.account_id.account_type == "liability_payable"
        )

    def _assert_entry(self, bill, voucher, amount_currency, balance=None):
        """Check the withholding entry of a voucher and its reconciliation."""
        balance = amount_currency if balance is None else balance
        wh_move = voucher.wh_move_id
        self.assertEqual(wh_move.state, "posted")
        self.assertEqual(wh_move.journal_id, self.wh_journal)
        self.assertEqual(wh_move.date, bill.date)
        self.assertEqual(len(wh_move.line_ids), 2)
        bill_payable = self._payable_lines(bill)
        wh_payable = wh_move.line_ids.filtered(
            lambda line: line.account_id == bill_payable.account_id
        )
        wh_liability = wh_move.line_ids.filtered(
            lambda line: line.account_id == self.wh_account
        )
        self.assertEqual(wh_payable.partner_id, bill.commercial_partner_id)
        self.assertEqual(wh_payable.currency_id, bill.currency_id)
        self.assertAlmostEqual(wh_payable.amount_currency, amount_currency, places=2)
        self.assertAlmostEqual(wh_payable.balance, balance, places=2)
        self.assertAlmostEqual(wh_liability.balance, -balance, places=2)
        self.assertTrue(wh_payable.reconciled)
        self.assertIn(
            bill_payable,
            wh_payable.matched_debit_ids.debit_move_id
            | wh_payable.matched_credit_ids.credit_move_id,
        )

    def _assert_voucher(self, bill, base, amount, subtrahend=0.0, concept=None):
        """Check the issued voucher of a concept; amounts are in bolivars."""
        voucher = bill.l10n_ve_islr_voucher_ids.filtered(
            lambda v: v.concept_id == (concept or self.concept) and v.state == "issued"
        )
        self.assertEqual(len(voucher), 1)
        self.assertEqual(voucher.source_move_id, bill)
        self.assertEqual(voucher.move_ids, bill)
        self.assertEqual(voucher.date, bill.date)
        self.assertEqual(voucher.partner_id, bill.commercial_partner_id)
        self.assertEqual(voucher.currency_id, self.ves)
        self.assertRegex(voucher.number, r"^202607\d{8}$")
        self.assertAlmostEqual(voucher.base, base, places=2)
        self.assertAlmostEqual(voucher.subtrahend, subtrahend, places=2)
        self.assertAlmostEqual(voucher.amount, amount, places=2)
        return voucher

    def _export_xml(self, month="07", company=None):
        export = self.env["l10n.ve.islr.xml.export"].create(
            {"company_id": (company or self.company).id, "year": "2026", "month": month}
        )
        export.action_generate()
        return ET.fromstring(base64.b64decode(export.file_data)).findall(
            "DetalleRetencion"
        )

    # Bill posting

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

    def test_post_pj_bill_creates_voucher_and_reconciled_entry(self):
        bill = self._create_bill(self.partner_pj, 1000.0)
        voucher = self._assert_voucher(bill, 100000.0, 5000.0)
        self.assertEqual(voucher.state, "issued")
        self.assertEqual(voucher.period, "202607")
        self.assertEqual(voucher.person_type, "pj_dom")
        self.assertAlmostEqual(voucher.rate, 5.0, places=2)
        self._assert_entry(bill, voucher, 50.0)
        self.assertAlmostEqual(bill.amount_residual, 950.0, places=2)
        self.assertEqual(bill.payment_state, "partial")
        self.assertFalse(bill.l10n_ve_islr_wh_pending)

    def test_post_pn_bill_with_subtrahend(self):
        # 100000 Bs x 3 % - UT 100 Bs x 3 % x 83,3334 = 2750 Bs = 27,50.
        bill = self._create_bill(self.partner_pn, 1000.0)
        voucher = self._assert_voucher(bill, 100000.0, 2750.0, subtrahend=250.0)
        self.assertEqual(voucher.person_type, "pn_res")
        self._assert_entry(bill, voucher, 27.5)
        self.assertAlmostEqual(bill.amount_residual, 972.5, places=2)

    def test_seeded_concepts_codes_and_subtrahend(self):
        # Tabla de conceptos del SENIAT (PNR / PJD) y Decreto 1.808 art. 9
        # parágrafo segundo: sustraendo en toda tarifa porcentual de PNR,
        # incluidas las de 1 %, salvo premios de loterías, juegos y apuestas.
        expected = {
            "islr_concept_honorarios": ("004", "002", True),
            "islr_concept_comisiones": ("020", "018", True),
            "islr_concept_servicios": ("055", "053", True),
            "islr_concept_intereses": ("027", "025", True),
            "islr_concept_arrendamiento_muebles": ("063", "061", True),
            "islr_concept_arrendamiento_inmuebles": ("059", "057", True),
            "islr_concept_fletes": ("072", "071", True),
            "islr_concept_publicidad": ("084", "083", True),
            "islr_concept_corredores_seguros": ("074", "073", True),
            "islr_concept_tarjetas_credito": ("067", "065", True),
            "islr_concept_premios_loterias": ("047", "045", False),
            "islr_concept_otros_premios": ("043", "041", False),
            "islr_concept_fondos_comercio": ("081", "079", True),
        }
        for xmlid, (code_pj, code_pn, subtrahend) in expected.items():
            concept = self.env.ref(f"l10n_ve_withholding_islr.{xmlid}")
            with self.subTest(concept=xmlid):
                self.assertEqual(concept.seniat_code_pj, code_pj)
                self.assertEqual(concept.seniat_code_pn, code_pn)
                self.assertEqual(concept.apply_subtrahend, subtrahend)

    def _pn_services_bill(self, amount):
        concept = self.env.ref("l10n_ve_withholding_islr.islr_concept_servicios")
        self.partner_pn.l10n_ve_islr_concept_id = concept
        return self._create_bill(self.partner_pn, amount), concept

    def test_pn_services_1pct_above_threshold(self):
        # UT 100 Bs y tasa 100 Bs por unidad: umbral 83,3334 UT = 83,33;
        # sustraendo 100 × 1 % × 83,3334 = 83,33 Bs; 916,67 Bs = 9,17.
        bill, concept = self._pn_services_bill(1000.0)
        voucher = self._assert_voucher(
            bill, 100000.0, 916.67, subtrahend=83.33, concept=concept
        )
        self.assertAlmostEqual(voucher.rate, 1.0, places=2)
        self.assertEqual(voucher.concept_id._get_seniat_code("pn_res"), "053")
        self.assertAlmostEqual(bill.amount_residual, 990.83, places=2)

    def test_pn_below_threshold_zero_voucher_without_entry(self):
        bill, concept = self._pn_services_bill(80.0)
        voucher = self._assert_voucher(
            bill, 8000.0, 0.0, subtrahend=83.33, concept=concept
        )
        self.assertEqual(voucher.state, "issued")
        self.assertFalse(voucher.wh_move_id)
        self.assertAlmostEqual(bill.amount_residual, 80.0, places=2)
        self.assertFalse(bill.l10n_ve_islr_wh_pending)

    def test_base_excludes_iva(self):
        bill = self._create_bill(self.partner_pj, 1000.0, taxes=self.tax_iva16_purchase)
        self.assertAlmostEqual(bill.amount_total, 1160.0, places=2)
        voucher = self._assert_voucher(bill, 100000.0, 5000.0)
        self._assert_entry(bill, voucher, 50.0)
        self.assertAlmostEqual(bill.amount_residual, 1110.0, places=2)

    def test_two_concepts_one_bill(self):
        bill = self._create_bill(
            self.partner_pj,
            lines=[
                {"price_unit": 600.0},
                {"price_unit": 300.0, "product_id": self.product_freight.id},
                {"price_unit": 100.0, "product_id": self.product_freight.id},
            ],
        )
        v1 = self._assert_voucher(bill, 60000.0, 3000.0)
        v2 = self._assert_voucher(bill, 40000.0, 1200.0, concept=self.concept_2)
        self.assertNotEqual(v1.number, v2.number)
        self.assertNotEqual(v1.wh_move_id, v2.wh_move_id)
        self._assert_entry(bill, v1, 30.0)
        self._assert_entry(bill, v2, 12.0)
        self.assertAlmostEqual(bill.amount_residual, 958.0, places=2)
        export = self.env["l10n.ve.islr.xml.export"].create(
            {"company_id": self.company.id, "year": "2026", "month": "07"}
        )
        export.action_generate()
        root = ET.fromstring(base64.b64decode(export.file_data))
        details = root.findall("DetalleRetencion")
        self.assertEqual(len(details), 2)
        self.assertEqual(
            {detail.findtext("CodigoConcepto") for detail in details}, {"004", "072"}
        )
        self.assertEqual(
            {detail.findtext("MontoOperacion") for detail in details},
            {"60000.00", "40000.00"},
        )
        self.assertEqual(
            {detail.findtext("NumeroFactura") for detail in details}, {"00012345"}
        )

    def test_line_without_concept_not_withheld(self):
        bill = self._create_bill(
            self.partner_plain,
            lines=[
                {"price_unit": 1000.0, "product_id": self.product_freight.id},
                {"price_unit": 500.0},
            ],
        )
        self.assertFalse(bill.invoice_line_ids[1].l10n_ve_islr_concept_id)
        self._assert_voucher(bill, 100000.0, 3000.0, concept=self.concept_2)
        self.assertAlmostEqual(bill.amount_residual, 1470.0, places=2)
        # A line whose concept is cleared on the draft bill is not withheld.
        bill_2 = self._create_bill(self.partner_pj, post=False)
        bill_2.invoice_line_ids.l10n_ve_islr_concept_id = False
        bill_2.action_post()
        self.assertFalse(bill_2.l10n_ve_islr_voucher_ids)
        self.assertAlmostEqual(bill_2.amount_residual, 1000.0, places=2)
        self.assertFalse(bill_2.l10n_ve_islr_wh_pending)
        with self.assertRaises(UserError):
            bill_2.action_l10n_ve_create_islr_wh()

    def test_concept_defaulted_from_product_then_partner(self):
        bill = self._create_bill(
            self.partner_pj,
            lines=[
                {"price_unit": 100.0, "product_id": self.product_freight.id},
                {"price_unit": 100.0},
            ],
            post=False,
        )
        lines = bill.invoice_line_ids
        self.assertEqual(lines[0].l10n_ve_islr_concept_id, self.concept_2)
        self.assertEqual(lines[1].l10n_ve_islr_concept_id, self.concept)
        bill_plain = self._create_bill(self.partner_plain, post=False)
        self.assertFalse(bill_plain.invoice_line_ids.l10n_ve_islr_concept_id)
        # Changing the product default later does not touch posted lines.
        bill.action_post()
        self.product_freight.l10n_ve_islr_concept_id = self.concept
        self.assertEqual(lines[0].l10n_ve_islr_concept_id, self.concept_2)

    def test_non_ve_company_untouched(self):
        other_data = self.setup_other_company(name="Other Company")
        other_company = other_data["company"]
        self.assertNotEqual(other_company.account_fiscal_country_id.code, "VE")
        other_company.l10n_ve_islr_wh_journal_id = other_data["default_journal_misc"]
        bill = self._create_bill(self.partner_pj, company_data=other_data)
        self.assertFalse(bill.invoice_line_ids.l10n_ve_islr_concept_id)
        self.assertFalse(bill.l10n_ve_islr_voucher_ids)
        self.assertEqual(bill.amount_residual, bill.amount_total)

    def test_foreign_currency_bill(self):
        # 1000 EUR at 2 EUR per USD = 500 USD = 50000 Bs: 2500 Bs withheld,
        # booked as 25 USD and 50 EUR.
        bill = self._create_bill(self.partner_pj, 1000.0, currency=self.eur)
        voucher = self._assert_voucher(bill, 50000.0, 2500.0)
        self._assert_entry(bill, voucher, 50.0, balance=25.0)
        wh_payable = voucher.wh_move_id.line_ids.filtered(
            lambda line: line.account_id == self._payable_lines(bill).account_id
        )
        self.assertFalse(wh_payable.matched_credit_ids.exchange_move_id)
        self.assertAlmostEqual(bill.amount_residual, 950.0, places=2)
        self.assertAlmostEqual(-bill.amount_residual_signed, 475.0, places=2)
        # The XML expresses the base in bolivars: 1000 EUR = 500 USD.
        export = self.env["l10n.ve.islr.xml.export"].create(
            {"company_id": self.company.id, "year": "2026", "month": "07"}
        )
        export.action_generate()
        root = ET.fromstring(base64.b64decode(export.file_data))
        self.assertEqual(
            root.find("DetalleRetencion").findtext("MontoOperacion"), "50000.00"
        )

    # Credit notes (Decree 1,808 art. 1; PA SNAT/2009/0095)

    def _full_refund(self, bill, date):
        return bill._reverse_moves(
            [{"date": date, "invoice_date": date, "ref": "NC-00000001"}],
            cancel=True,
        )

    def test_credit_note_total_same_month_cancels_voucher(self):
        bill = self._create_bill(self.partner_pj)
        voucher = bill.l10n_ve_islr_voucher_ids
        refund = self._full_refund(bill, "2026-07-20")
        self.assertEqual(refund.state, "posted")
        self.assertFalse(refund.l10n_ve_islr_voucher_ids)
        self.assertEqual(voucher.state, "cancelled")
        self.assertEqual(voucher.credit_note_id, refund)
        self.assertEqual(voucher.wh_move_id.state, "cancel")
        self.assertFalse(
            bill.l10n_ve_islr_voucher_ids.filtered(lambda v: v.state == "issued")
        )
        self.assertFalse(bill.l10n_ve_islr_wh_pending)
        self.assertAlmostEqual(bill.amount_residual, 0.0, places=2)
        self.assertAlmostEqual(refund.amount_residual, 0.0, places=2)
        # Neither document is declared: only the no-operations row remains.
        details = self._export_xml()
        self.assertEqual(len(details), 1)
        self.assertEqual(details[0].findtext("CodigoConcepto"), "000")

    def test_credit_note_partial_same_month_nets_voucher(self):
        bill = self._create_bill(self.partner_pj)
        original = bill.l10n_ve_islr_voucher_ids
        refund = self._create_bill(
            self.partner_pj,
            400.0,
            bill_date="2026-07-25",
            ref="NC-00000002",
            move_type="in_refund",
            reversed_entry=bill,
        )
        self.assertFalse(refund.l10n_ve_islr_voucher_ids)
        self.assertEqual(original.state, "cancelled")
        self.assertEqual(original.credit_note_id, refund)
        # Net base 600 USD = 60000 Bs x 5 % = 3000 Bs = 30 USD.
        voucher = self._assert_voucher(bill, 60000.0, 3000.0)
        self.assertNotEqual(voucher, original)
        self._assert_entry(bill, voucher, 30.0)
        self.assertFalse(bill.l10n_ve_islr_wh_pending)
        # The payable drops by exactly the net withholding.
        self.assertAlmostEqual(bill.amount_residual, 570.0, places=2)
        self.assertAlmostEqual(refund.amount_residual, 0.0, places=2)
        partner_balance = sum(
            self.env["account.move.line"]
            .search(
                [
                    ("partner_id", "=", self.partner_pj.id),
                    ("account_id", "=", self._payable_lines(bill).account_id.id),
                    ("parent_state", "=", "posted"),
                ]
            )
            .mapped("balance")
        )
        self.assertAlmostEqual(partner_balance, -570.0, places=2)
        details = self._export_xml()
        self.assertEqual(len(details), 1)
        detail = details[0]
        self.assertEqual(detail.findtext("NumeroFactura"), "00012345")
        self.assertEqual(detail.findtext("MontoOperacion"), "60000.00")
        self.assertEqual(detail.findtext("PorcentajeRetencion"), "5.00")
        # The credit note that adjusted the voucher cannot be undone.
        with self.assertRaisesRegex(UserError, "ajustó la retención"):
            refund.button_draft()
        with self.assertRaisesRegex(UserError, "ajustó la retención"):
            refund.button_cancel()
        self.assertEqual(refund.state, "posted")

    def test_credit_note_partial_resident_individual_subtrahend(self):
        bill = self._create_bill(self.partner_pn)
        self._create_bill(
            self.partner_pn,
            400.0,
            move_type="in_refund",
            ref="NC-00000003",
            reversed_entry=bill,
        )
        # 60000 Bs x 3 % - 250 Bs of subtrahend = 1550 Bs = 15,50 USD.
        voucher = self._assert_voucher(bill, 60000.0, 1550.0, subtrahend=250.0)
        self._assert_entry(bill, voucher, 15.5)
        self.assertAlmostEqual(bill.amount_residual, 584.5, places=2)

    def test_credit_note_later_month_leaves_voucher(self):
        bill = self._create_bill(self.partner_pj)
        voucher = bill.l10n_ve_islr_voucher_ids
        refund = self._full_refund(bill, "2026-08-10")
        self.assertFalse(refund.l10n_ve_islr_voucher_ids)
        self.assertEqual(voucher.state, "issued")
        self.assertFalse(voucher.credit_note_id)
        self._assert_entry(bill, voucher, 50.0)
        # The declared withholding stays: the vendor owes it back.
        self.assertAlmostEqual(bill.amount_residual, 0.0, places=2)
        self.assertAlmostEqual(refund.amount_residual, 50.0, places=2)
        july = self._export_xml("07")
        self.assertEqual(len(july), 1)
        self.assertEqual(july[0].findtext("MontoOperacion"), "100000.00")
        august = self._export_xml("08")
        self.assertEqual(len(august), 1)
        self.assertEqual(august[0].findtext("CodigoConcepto"), "000")
        # A partial credit note of a later month changes nothing either.
        bill_2 = self._create_bill(self.partner_pj, ref="FAC-00012399")
        voucher_2 = bill_2.l10n_ve_islr_voucher_ids
        refund_2 = self._create_bill(
            self.partner_pj,
            300.0,
            bill_date="2026-08-03",
            ref="NC-00000004",
            move_type="in_refund",
            reversed_entry=bill_2,
        )
        self.assertEqual(voucher_2.state, "issued")
        self.assertFalse(refund_2.l10n_ve_islr_voucher_ids)
        refund_2.button_draft()
        self.assertEqual(refund_2.state, "draft")

    def test_credit_note_without_voucher_does_nothing(self):
        refund = self._create_bill(self.partner_pj, 200.0, move_type="in_refund")
        self.assertFalse(refund.l10n_ve_islr_voucher_ids)
        self.assertAlmostEqual(refund.amount_residual, 200.0, places=2)
        self.assertFalse(refund.l10n_ve_islr_wh_pending)
        refund.button_draft()
        # Bill whose voucher was cancelled beforehand.
        bill = self._create_bill(self.partner_pj)
        voucher = bill.l10n_ve_islr_voucher_ids
        voucher.action_cancel()
        refund_2 = self._create_bill(
            self.partner_pj,
            200.0,
            move_type="in_refund",
            ref="NC-00000005",
            reversed_entry=bill,
        )
        self.assertFalse(refund_2.l10n_ve_islr_voucher_ids)
        self.assertFalse(voucher.credit_note_id)
        self.assertEqual(
            bill.l10n_ve_islr_voucher_ids.filtered(lambda v: v.state != "cancelled"),
            self.env["l10n.ve.islr.voucher"],
        )

    def test_bill_repost_nets_same_month_credit_note(self):
        bill = self._create_bill(self.partner_pj)
        self._create_bill(
            self.partner_pj,
            400.0,
            move_type="in_refund",
            ref="NC-00000006",
            reversed_entry=bill,
        )
        bill.button_draft()
        self.assertFalse(
            bill.l10n_ve_islr_voucher_ids.filtered(lambda v: v.state == "issued")
        )
        bill.action_post()
        voucher = self._assert_voucher(bill, 60000.0, 3000.0)
        self._assert_entry(bill, voucher, 30.0)

    def test_net_voucher_keeps_snapshotted_person_type(self):
        bill = self._create_bill(self.partner_pn)
        self.assertEqual(bill.l10n_ve_islr_voucher_ids.person_type, "pn_res")
        self.partner_pn.l10n_ve_person_type = "pj_dom"
        self._create_bill(
            self.partner_pn,
            400.0,
            move_type="in_refund",
            ref="NC-00000007",
            reversed_entry=bill,
        )
        # Still 3 % with subtrahend, not the 5 % of the new person type.
        voucher = self._assert_voucher(bill, 60000.0, 1550.0, subtrahend=250.0)
        self.assertEqual(voucher.person_type, "pn_res")
        self.assertAlmostEqual(voucher.rate, 3.0, places=2)

    # Vendor RIF

    def test_vendor_rif_required_for_withholding(self):
        for vat in (False, "J-9876543", "X-98765432-1", "J-98765432-1"):
            with self.subTest(vat=vat):
                self.partner_pj.with_context(no_vat_validation=True).vat = vat
                bill = self._create_bill(self.partner_pj, post=False)
                with self.assertRaisesRegex(UserError, "Proveedor PJ Domiciliada"):
                    bill.action_post()
                self.assertEqual(bill.state, "draft")
        for vat in ("J-98765432-4", "j 98765432 4", "J987654324"):
            with self.subTest(vat=vat):
                self.partner_pj.with_context(no_vat_validation=True).vat = vat
                bill = self._create_bill(self.partner_pj)
                self.assertEqual(bill.state, "posted")
        details = self._export_xml()
        self.assertEqual(
            {detail.findtext("RifRetenido") for detail in details}, {"J987654324"}
        )
        # The natural person fixture is valid too.
        self.assertEqual(self._create_bill(self.partner_pn).state, "posted")

    def test_vendor_without_rif_posts_bill_without_concept(self):
        self.partner_plain.with_context(no_vat_validation=True).vat = False
        bill = self._create_bill(self.partner_plain)
        self.assertEqual(bill.state, "posted")
        self.assertFalse(bill.l10n_ve_islr_voucher_ids)
        # Credit notes are not checked: they never issue a voucher.
        self.partner_pj.with_context(no_vat_validation=True).vat = False
        refund = self._create_bill(self.partner_pj, move_type="in_refund")
        self.assertTrue(refund.invoice_line_ids.l10n_ve_islr_concept_id)
        self.assertEqual(refund.state, "posted")

    def test_negative_voucher_rejected(self):
        for field in ("base", "amount", "subtrahend"):
            with self.subTest(field=field), self.assertRaises(ValidationError):
                self.env["l10n.ve.islr.voucher"].create(
                    {
                        "date": BILL_DATE,
                        "partner_id": self.partner_pj.id,
                        "concept_id": self.concept.id,
                        field: -1.0,
                    }
                )

    def test_reset_to_draft_and_repost(self):
        bill = self._create_bill(self.partner_pj)
        voucher = bill.l10n_ve_islr_voucher_ids
        number = voucher.number
        wh_move = voucher.wh_move_id
        with self.assertRaises(UserError):
            wh_move.button_draft()
        bill.button_draft()
        self.assertEqual(voucher.state, "cancelled")
        self.assertEqual(voucher.number, number)
        self.assertEqual(wh_move.state, "cancel")
        self.assertFalse(self._payable_lines(bill).matched_debit_ids)
        bill.action_post()
        new_voucher = self._assert_voucher(bill, 100000.0, 5000.0)
        self.assertNotEqual(new_voucher, voucher)
        self.assertEqual(int(new_voucher.number), int(number) + 1)
        self._assert_entry(bill, new_voucher, 50.0)
        self.assertAlmostEqual(bill.amount_residual, 950.0, places=2)

    def test_cancel_bill_cancels_voucher(self):
        bill = self._create_bill(self.partner_pj)
        voucher = bill.l10n_ve_islr_voucher_ids
        bill.button_cancel()
        self.assertEqual(bill.state, "cancel")
        self.assertEqual(voucher.state, "cancelled")
        self.assertEqual(voucher.wh_move_id.state, "cancel")

    def test_payment_after_posting_pays_net_only(self):
        bill = self._create_bill(self.partner_pj)
        wizard = (
            self.env["account.payment.register"]
            .with_context(active_model="account.move", active_ids=bill.ids)
            .create({"payment_date": "2026-07-20"})
        )
        self.assertAlmostEqual(wizard.amount, 950.0, places=2)
        payments = wizard._create_payments()
        self.assertAlmostEqual(payments.amount, 950.0, places=2)
        self.assertIn(bill.payment_state, ("paid", "in_payment"))
        self.assertFalse(
            payments.move_id.line_ids.filtered(
                lambda line: line.account_id == self.wh_account
            )
        )
        self.assertEqual(
            self.env["l10n.ve.islr.voucher"].search_count(
                [("move_ids", "in", bill.ids)]
            ),
            1,
        )

    def test_multi_record_post(self):
        bill_pj = self._create_bill(self.partner_pj, post=False)
        bill_pn = self._create_bill(self.partner_pn, post=False)
        bill_plain = self._create_bill(self.partner_plain, 300.0, post=False)
        (bill_pj + bill_pn + bill_plain).action_post()
        v_pj = self._assert_voucher(bill_pj, 100000.0, 5000.0)
        v_pn = self._assert_voucher(bill_pn, 100000.0, 2750.0, subtrahend=250.0)
        self.assertFalse(bill_plain.l10n_ve_islr_voucher_ids)
        self.assertNotEqual(v_pj.number, v_pn.number)
        self._assert_entry(bill_pj, v_pj, 50.0)
        self._assert_entry(bill_pn, v_pn, 27.5)

    def test_missing_configuration_raises(self):
        self.company.l10n_ve_islr_wh_journal_id = False
        bill = self._create_bill(self.partner_pj, post=False)
        with self.assertRaisesRegex(UserError, "configure el diario"):
            bill.action_post()
        self.company.l10n_ve_islr_wh_journal_id = self.wh_journal
        self.company.l10n_ve_islr_wh_account_id = False
        bill_2 = self._create_bill(self.partner_pj, post=False)
        with self.assertRaisesRegex(UserError, "configure el diario"):
            bill_2.action_post()

    def test_button_reissues_after_voucher_cancelled(self):
        bill = self._create_bill(self.partner_pj)
        voucher = bill.l10n_ve_islr_voucher_ids
        voucher.action_cancel()
        self.assertEqual(voucher.wh_move_id.state, "cancel")
        self.assertAlmostEqual(bill.amount_residual, 1000.0, places=2)
        self.assertTrue(bill.l10n_ve_islr_wh_pending)
        bill.action_l10n_ve_create_islr_wh()
        new_voucher = self._assert_voucher(bill, 100000.0, 5000.0)
        self.assertNotEqual(new_voucher, voucher)
        self.assertAlmostEqual(bill.amount_residual, 950.0, places=2)
        with self.assertRaises(UserError):
            bill.action_l10n_ve_create_islr_wh()

    def test_missing_ves_rate_blocks_subtrahend(self):
        self.env["res.currency.rate"].search(
            [("currency_id", "=", self.ves.id)]
        ).unlink()
        bill = self._create_bill(self.partner_pn, post=False)
        with self.assertRaises(UserError):
            bill.action_post()

    # Security

    def test_invoicing_user_can_post_and_reset(self):
        user = new_test_user(
            self.env,
            login="islr_billing",
            groups="base.group_user,account.group_account_invoice",
            company_id=self.company.id,
            company_ids=[Command.set(self.company.ids)],
        )
        self.assertFalse(user.has_group("account.group_account_manager"))
        bill = self._create_bill(self.partner_pn, user=user)
        self.assertEqual(bill.env.uid, user.id)
        self.assertAlmostEqual(bill.amount_residual, 972.5, places=2)
        voucher = bill.l10n_ve_islr_voucher_ids
        self.assertEqual(voucher.state, "issued")
        with self.assertRaises(AccessError):
            self.env["l10n.ve.islr.voucher"].with_user(user).create(
                {
                    "partner_id": self.partner_pj.id,
                    "concept_id": self.concept.id,
                }
            )
        bill.button_draft()
        self.assertEqual(voucher.sudo().state, "cancelled")
        self.assertEqual(voucher.sudo().wh_move_id.state, "cancel")

    def test_invoicing_user_cannot_write_concepts_or_ut(self):
        user = new_test_user(
            self.env,
            login="islr_billing_ro",
            groups="base.group_user,account.group_account_invoice",
            company_id=self.company.id,
            company_ids=[Command.set(self.company.ids)],
        )
        self.assertTrue(self.concept.with_user(user).name)
        with self.assertRaises(AccessError):
            self.concept.with_user(user).write({"rate_pj_dom": 1.0})
        with self.assertRaises(AccessError):
            self.ut_current.with_user(user).write({"value": 1.0})
        with self.assertRaises(AccessError):
            self.env["l10n.ve.ut"].with_user(user).create(
                {"date_from": "2026-09-01", "value": 1.0}
            )

    def test_issued_voucher_rejects_fiscal_writes(self):
        bill = self._create_bill(self.partner_pj)
        voucher = bill.l10n_ve_islr_voucher_ids
        for vals in (
            {"amount": 1.0},
            {"base": 1.0},
            {"partner_id": self.partner_pn.id},
            {"concept_id": self.concept_2.id},
            {"date": "2026-07-01"},
            {"number": "20260799999999"},
            {"move_ids": [Command.clear()]},
            {"state": "draft"},
        ):
            with self.subTest(vals=vals), self.assertRaises(UserError):
                voucher.with_context(l10n_ve_islr_voucher_internal=True).write(vals)
        with self.assertRaises(UserError):
            voucher.action_issue()
        voucher.action_cancel()
        with self.assertRaises(UserError):
            voucher.action_cancel()
        with self.assertRaises(UserError):
            voucher.write({"amount": 1.0})

    def test_manual_voucher_state_flow(self):
        voucher = self.env["l10n.ve.islr.voucher"].create(
            {
                "date": BILL_DATE,
                "partner_id": self.partner_pj.id,
                "concept_id": self.concept.id,
                "base": 100.0,
                "rate": 5.0,
                "amount": 5.0,
            }
        )
        voucher.amount = 4.0
        voucher.action_issue()
        self.assertEqual(voucher.state, "issued")
        number = voucher.number
        # No transition leads back to draft: cancelling is the only way out.
        self.assertFalse(hasattr(voucher, "action_draft"))
        with self.assertRaises(UserError):
            voucher.write({"state": "draft"})
        with self.assertRaises(UserError):
            voucher.unlink()
        voucher.action_cancel()
        self.assertEqual(voucher.state, "cancelled")
        self.assertEqual(voucher.number, number)
        with self.assertRaises(UserError):
            voucher.write({"state": "draft"})
        with self.assertRaises(UserError):
            voucher.unlink()
        self.assertEqual(voucher.number, number)

    def test_voucher_number_only_from_sequence(self):
        vals = {
            "date": BILL_DATE,
            "partner_id": self.partner_pj.id,
            "concept_id": self.concept.id,
            "base": 100.0,
            "rate": 5.0,
            "amount": 5.0,
        }
        model = self.env["l10n.ve.islr.voucher"]
        for number in ("20260799999999", "/", False):
            with self.subTest(number=number), self.assertRaises(UserError):
                model.create(dict(vals, number=number))
        # The number is assigned at create, from the monthly sequence.
        # create() writes the number into the vals it receives: copy them.
        first = model.create(dict(vals))
        second = model.create(dict(vals))
        self.assertRegex(first.number, r"^202607\d{8}$")
        self.assertEqual(int(second.number), int(first.number) + 1)
        for number in ("20260799999999", first.number, "/", False):
            with self.subTest(write=number), self.assertRaises(UserError):
                first.write({"number": number})
        # Only drafts can be deleted.
        second.unlink()
        self.assertFalse(second.exists())

    def test_wh_entry_reset_blocked_with_any_context(self):
        bill = self._create_bill(self.partner_pj)
        wh_move = bill.l10n_ve_islr_voucher_ids.wh_move_id
        for ctx in (
            {},
            {"l10n_ve_islr_wh_undo": True},
            {"l10n_ve_iva_wh_undo": True},
            {"l10n_ve_islr_voucher_internal": True},
        ):
            with self.subTest(ctx=ctx), self.assertRaises(UserError):
                wh_move.with_context(**ctx).button_draft()
        self.assertEqual(wh_move.state, "posted")

    def test_other_company_user_cannot_read_voucher(self):
        bill = self._create_bill(self.partner_pj)
        voucher = bill.l10n_ve_islr_voucher_ids
        other_company = self.setup_other_company(name="Other Company")["company"]
        user = new_test_user(
            self.env,
            login="islr_other_company",
            groups="base.group_user,account.group_account_manager",
            company_id=other_company.id,
            company_ids=[Command.set(other_company.ids)],
        )
        voucher.invalidate_recordset()
        with self.assertRaises(AccessError):
            voucher.with_user(user).with_context(
                allowed_company_ids=other_company.ids
            ).read(["number"])
        export = self.env["l10n.ve.islr.xml.export"].create(
            {"company_id": other_company.id, "year": "2026", "month": "07"}
        )
        with self.assertRaises(UserError):
            export.with_context(allowed_company_ids=self.company.ids).action_generate()

    # XML export and sequence

    def test_missing_ves_rate_blocks_xml_export(self):
        # Vouchers issued from bills are in bolivars and need no rate; a
        # manual voucher in another currency does.
        self._create_bill(self.partner_pj)
        self.env["res.currency.rate"].search(
            [("currency_id", "=", self.ves.id)]
        ).unlink()
        self.assertEqual(len(self._export_xml()), 1)
        manual = self.env["l10n.ve.islr.voucher"].create(
            {
                "date": BILL_DATE,
                "partner_id": self.partner_pj.id,
                "concept_id": self.concept.id,
                "base": 100.0,
                "rate": 5.0,
                "amount": 5.0,
            }
        )
        manual.action_issue()
        self.assertNotEqual(manual.currency_id, self.ves)
        export = self.env["l10n.ve.islr.xml.export"].create(
            {"company_id": self.company.id, "year": "2026", "month": "07"}
        )
        with self.assertRaises(UserError):
            export.action_generate()

    def test_placeholder_seniat_code_blocks_export(self):
        # Posting and issuing reject such a concept; a voucher created
        # directly in the issued state is still caught by the export.
        concept_000 = self.env["l10n.ve.islr.concept"].create(
            {
                "name": "Concepto sin código confirmado",
                "rate_pj_dom": 2.0,
            }
        )
        self.env["l10n.ve.islr.voucher"]._l10n_ve_create_unlocked(
            {
                "date": BILL_DATE,
                "partner_id": self.partner_pj.id,
                "concept_id": concept_000.id,
                "base": 500.0,
                "rate": 2.0,
                "amount": 10.0,
                "state": "issued",
            }
        )
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
        self.assertEqual(detail.findtext("RifRetenido"), "J123456784")
        self.assertEqual(detail.findtext("FechaOperacion"), "28/02/2026")
        self.assertEqual(detail.findtext("MontoOperacion"), "0.00")
        self.assertEqual(detail.findtext("PorcentajeRetencion"), "0.00")

    def test_sequence_per_company_monthly_reset(self):
        bill_july = self._create_bill(self.partner_pj, 100.0)
        self.assertEqual(bill_july.l10n_ve_islr_voucher_ids.number, "20260700000001")
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
        bill_august = self._create_bill(self.partner_pj, 100.0, bill_date="2026-08-05")
        voucher_august = bill_august.l10n_ve_islr_voucher_ids
        self.assertEqual(voucher_august.number, "20260800000001")
        self.assertEqual(voucher_august.period, "202608")

    def test_xml_export(self):
        self._create_bill(self.partner_pj, 1000.0)
        self._create_bill(self.partner_pn, 50.0, ref="FAC-00012346")

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
            export.file_name, "RelacionRetencionesISLR_J123456784_202607.xml"
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
            self.assertEqual(detail.findtext("FechaOperacion"), "15/07/2026")
            self.assertRegex(detail.findtext("CodigoConcepto"), r"^\d{3}$")
            self.assertRegex(detail.findtext("MontoOperacion"), r"^\d+\.\d{2}$")
            self.assertRegex(detail.findtext("NumeroFactura"), r"^\d{1,10}$")
            self.assertTrue(detail.findtext("NumeroControl"))
        amounts = [detail.findtext("MontoOperacion") for detail in details]
        self.assertIn("100000.00", amounts)
        self.assertIn("5000.00", amounts)

    # Rounding in foreign currency

    def test_ves_company_usd_bill_rounding(self):
        # The withholding is computed on the bolivars booked by the bill,
        # rounded, and only then converted to dollars.
        ves_data = self.setup_other_company(
            name="Compania VES", currency_id=self.ves.id
        )
        company = ves_data["company"]
        self.change_company_country(company, self.env.ref("base.ve"))
        company.with_context(no_vat_validation=True).vat = "J-12345678-4"
        company.l10n_ve_islr_wh_account_id = (
            self.env["account.account"]
            .with_company(company)
            .create(
                {
                    "code": "210402",
                    "name": "Retenciones de ISLR por Enterar",
                    "account_type": "liability_current",
                }
            )
        )
        company.l10n_ve_islr_wh_journal_id = ves_data["default_journal_misc"]
        usd = self.company.currency_id
        self.env["res.currency.rate"].create(
            {
                "currency_id": usd.id,
                "name": "2026-01-01",
                "rate": 1.0 / 46.3842,
                "company_id": company.id,
            }
        )
        bill = self._create_bill(
            self.partner_pj, 1234.57, currency=usd, company_data=ves_data
        )
        self.assertAlmostEqual(bill.invoice_line_ids.balance, 57264.54, places=2)
        voucher = bill.l10n_ve_islr_voucher_ids
        self.assertEqual(voucher.currency_id, self.ves)
        self.assertAlmostEqual(voucher.base, 57264.54, places=2)
        # 57264,54 x 5 % = 2863,23 Bs (61,73 USD x 46,3842 would be 2863,30).
        self.assertAlmostEqual(voucher.amount, 2863.23, places=2)
        wh_payable = voucher.wh_move_id.line_ids.filtered(
            lambda line: line.account_id == self._payable_lines(bill).account_id
        )
        self.assertAlmostEqual(wh_payable.balance, 2863.23, places=2)
        self.assertAlmostEqual(wh_payable.amount_currency, 61.73, places=2)
        self.assertTrue(wh_payable.reconciled)
        self.assertAlmostEqual(bill.amount_residual, 1172.84, places=2)
        # Paying the dollar residual settles the bill; any cent left in
        # bolivars goes to the standard exchange difference.
        wizard = (
            self.env["account.payment.register"]
            .with_company(company)
            .with_context(active_model="account.move", active_ids=bill.ids)
            .create({"payment_date": BILL_DATE})
        )
        wizard._create_payments()
        self.assertIn(bill.payment_state, ("paid", "in_payment"))
        self.assertAlmostEqual(voucher.amount, 2863.23, places=2)
        self.assertAlmostEqual(voucher.base, 57264.54, places=2)

    # Hardening of the withholding entry

    def _accountant(self, login="islr_accountant"):
        return new_test_user(
            self.env,
            login=login,
            groups="base.group_user,account.group_account_manager",
            company_id=self.company.id,
            company_ids=[Command.set(self.company.ids)],
        )

    def test_wh_entry_locked_while_voucher_issued(self):
        bill = self._create_bill(self.partner_pj)
        voucher = bill.l10n_ve_islr_voucher_ids
        user = self._accountant()
        wh_move = voucher.wh_move_id.with_user(user)
        bill_payable = self._payable_lines(bill).with_user(user)
        wh_payable = wh_move.line_ids.filtered(
            lambda line: line.account_id == bill_payable.account_id
        )
        actions = {
            "draft": wh_move.button_draft,
            "cancel": wh_move.button_cancel,
            "reverse": lambda: wh_move._reverse_moves(
                [{"date": BILL_DATE}], cancel=True
            ),
            "reverse_draft": lambda: wh_move._reverse_moves([{"date": BILL_DATE}]),
            "unlink": wh_move.unlink,
            "unreconcile_wh": wh_payable.remove_move_reconcile,
            "unreconcile_bill": bill_payable.remove_move_reconcile,
            "unlink_partial": (
                wh_payable.matched_debit_ids | wh_payable.matched_credit_ids
            ).unlink,
        }
        for name, action in actions.items():
            with self.subTest(action=name), self.assertRaises(UserError):
                action()
        self.assertEqual(wh_move.state, "posted")
        self.assertTrue(wh_payable.reconciled)
        reversal = (
            self.env["account.move.reversal"]
            .with_user(user)
            .with_context(active_model="account.move", active_ids=wh_move.ids)
            .create({"date": BILL_DATE, "journal_id": self.wh_journal.id})
        )
        with self.assertRaises(UserError):
            reversal.modify_moves()
        # The legitimate path: cancelling the voucher undoes the entry.
        voucher.with_user(user).action_cancel()
        self.assertEqual(wh_move.state, "cancel")
        self.assertAlmostEqual(bill.amount_residual, 1000.0, places=2)

    def test_payment_unreconcile_keeps_wh_entry(self):
        bill = self._create_bill(self.partner_pj)
        voucher = bill.l10n_ve_islr_voucher_ids
        payments = (
            self.env["account.payment.register"]
            .with_context(active_model="account.move", active_ids=bill.ids)
            .create({"payment_date": "2026-07-20"})
            ._create_payments()
        )
        self.assertIn(bill.payment_state, ("paid", "in_payment"))
        user = self._accountant("islr_accountant_pay")
        payment_line = payments.move_id.line_ids.with_user(user).filtered(
            lambda line: line.account_id == self._payable_lines(bill).account_id
        )
        payment_line.remove_move_reconcile()
        self.assertAlmostEqual(bill.amount_residual, 950.0, places=2)
        self._assert_entry(bill, voucher, 50.0)

    # Non-residents (Decree 1,808 art. 9; Income Tax Law, Tarifa N° 2)

    def _issued(self, bill, concept=None):
        return bill.l10n_ve_islr_voucher_ids.filtered(
            lambda v: v.state == "issued" and v.concept_id == (concept or v.concept_id)
        )

    def _assert_t2(self, bill, taxable_base, amount, rate):
        voucher = self._issued(bill)
        self.assertEqual(len(voucher), 1)
        self.assertTrue(voucher.is_tarifa2)
        self.assertFalse(voucher.treaty_applied)
        self.assertAlmostEqual(voucher.taxable_base, taxable_base, places=2)
        self.assertAlmostEqual(voucher.amount, amount, places=2)
        self.assertAlmostEqual(voucher.rate, rate, places=2)
        self.assertAlmostEqual(voucher.subtrahend, 0.0, places=2)
        return voucher

    def test_foreign_fixture_rif_is_valid(self):
        self.assertTrue(is_valid_rif("J456789012"))
        self.assertTrue(self.partner_foreign._l10n_ve_islr_get_valid_rif())

    def test_seeded_nonresident_concepts(self):
        expected = {
            "islr_concept_honorarios": ("003", 34.0, 90.0, "005", "tarifa2", 90.0),
            "islr_concept_comisiones": ("019", 34.0, 100.0, "021", "fixed", 100.0),
            "islr_concept_servicios": ("054", 34.0, 100.0, "056", "tarifa2", 100.0),
            "islr_concept_canones_regalias": (
                "034",
                34.0,
                90.0,
                "035",
                "tarifa2",
                90.0,
            ),
            "islr_concept_fletes_internacionales": (
                "000",
                0.0,
                100.0,
                "030",
                "tarifa2",
                5.0,
            ),
            "islr_concept_primas_seguro": ("000", 0.0, 100.0, "040", "fixed", 30.0),
            "islr_concept_fletes_internacionales_pais": (
                "000",
                0.0,
                100.0,
                "031",
                "tarifa2",
                10.0,
            ),
            "islr_concept_asistencia_tecnica": (
                "036",
                34.0,
                30.0,
                "037",
                "tarifa2",
                30.0,
            ),
            "islr_concept_servicios_tecnologicos": (
                "038",
                34.0,
                50.0,
                "039",
                "tarifa2",
                50.0,
            ),
            "islr_concept_intereses_inst_financieras": (
                "000",
                0.0,
                100.0,
                "024",
                "fixed",
                100.0,
            ),
        }
        for xmlid, values in expected.items():
            concept = self.env.ref(f"l10n_ve_withholding_islr.{xmlid}")
            with self.subTest(concept=xmlid):
                self.assertEqual(
                    (
                        concept.seniat_code_pn_nores,
                        concept.rate_pn_nores,
                        concept.base_pct_pn_nores,
                        concept.seniat_code_pj_nodom,
                        concept.pj_nodom_rate_type,
                        concept.base_pct_pj_nodom,
                    ),
                    values,
                )
        self.assertAlmostEqual(
            self.env.ref(
                "l10n_ve_withholding_islr.islr_concept_intereses_inst_financieras"
            ).rate_pj_nodom,
            4.95,
            places=2,
        )
        # Resident results are unchanged: no seeded concept has a presumptive
        # base for residents.
        concepts = (
            self.env["l10n.ve.islr.concept"].with_context(active_test=False).search([])
        )
        self.assertEqual(set(concepts.mapped("base_pct_pj_dom")), {100.0})
        self.assertEqual(set(concepts.mapped("base_pct_pn_res")), {100.0})

    def test_base_pct_and_treaty_rate_bounds(self):
        with self.assertRaises(ValidationError):
            self.concept.base_pct_pj_nodom = 120.0
        with self.assertRaises(ValidationError):
            self.partner_foreign.l10n_ve_islr_treaty_rate = 150.0

    def test_pn_nonresident_fixed_rate_without_subtrahend(self):
        # 100000 Bs x 90 % = 90000 Bs x 34 % = 30600 Bs = 306 USD; the
        # concept applies the subtrahend, but only to residents.
        self.partner_pn.l10n_ve_person_type = "pn_nores"
        self.assertAlmostEqual(self.partner_pn.l10n_ve_islr_rate, 34.0, places=2)
        bill = self._create_bill(self.partner_pn, 1000.0)
        voucher = self._assert_voucher(bill, 100000.0, 30600.0)
        self.assertEqual(voucher.person_type, "pn_nores")
        self.assertAlmostEqual(voucher.base_pct, 90.0, places=2)
        self.assertAlmostEqual(voucher.taxable_base, 90000.0, places=2)
        self.assertAlmostEqual(voucher.rate, 34.0, places=2)
        self.assertFalse(voucher.is_tarifa2)
        self._assert_entry(bill, voucher, 306.0)
        self.assertAlmostEqual(bill.amount_residual, 694.0, places=2)

    def test_tarifa2_cumulative_brackets_and_year_reset(self):
        # UT 100 Bs: brackets at 200000 Bs and 300000 Bs of taxable base.
        # Each bill: 4000 USD = 400000 Bs x 30 % = 120000 Bs taxable.
        bill_1 = self._create_bill(self.partner_foreign, 4000.0, "2026-03-10")
        voucher_1 = self._assert_t2(bill_1, 120000.0, 18000.0, 15.0)
        self.assertEqual(voucher_1.person_type, "pj_nodom")
        self.assertAlmostEqual(voucher_1.base, 400000.0, places=2)
        self.assertAlmostEqual(voucher_1.base_pct, 30.0, places=2)
        self._assert_entry(bill_1, voucher_1, 180.0)
        # A cancelled voucher does not count.
        bill_draft = self._create_bill(self.partner_foreign, 4000.0, "2026-03-20")
        bill_draft.button_draft()
        self.assertEqual(bill_draft.l10n_ve_islr_voucher_ids.state, "cancelled")
        # 240000 Bs: 200000 x 15 % + 40000 x 22 % = 38800 - 18000.
        bill_2 = self._create_bill(self.partner_foreign, 4000.0, "2026-04-10")
        self._assert_t2(bill_2, 120000.0, 20800.0, 17.33)
        # 360000 Bs: 30000 + 22000 + 60000 x 34 % = 72400 - 38800.
        bill_3 = self._create_bill(self.partner_foreign, 4000.0, "2026-05-10")
        self._assert_t2(bill_3, 120000.0, 33600.0, 28.0)
        # Another vendor starts its own accumulation.
        other = self.partner_foreign.with_context(no_vat_validation=True).copy(
            {"name": "Otro Proveedor No Domiciliado"}
        )
        self._assert_t2(
            self._create_bill(other, 4000.0, "2026-05-11"), 120000.0, 18000.0, 15.0
        )
        # The next calendar year starts again from the first bracket.
        bill_next = self._create_bill(self.partner_foreign, 4000.0, "2027-01-15")
        self._assert_t2(bill_next, 120000.0, 18000.0, 15.0)

    def test_tarifa2_ut_change_between_bills(self):
        concept = self.env.ref("l10n_ve_withholding_islr.islr_concept_servicios")
        self.partner_foreign.l10n_ve_islr_concept_id = concept
        self.env["l10n.ve.ut"].create({"date_from": "2026-08-01", "value": 200.0})
        # 150000 Bs with UT 100: first bracket, 22500 Bs.
        bill_1 = self._create_bill(self.partner_foreign, 1500.0, "2026-07-10")
        self._assert_t2(bill_1, 150000.0, 22500.0, 15.0)
        # 300000 Bs accumulated with UT 200 (bracket at 400000 Bs): still
        # 15 %. With UT 100 it would have been 52000 - 22500 = 29500 Bs.
        bill_2 = self._create_bill(self.partner_foreign, 1500.0, "2026-08-10")
        voucher = self._assert_t2(bill_2, 150000.0, 22500.0, 15.0)
        self.assertEqual(voucher.concept_id._get_seniat_code("pj_nodom"), "056")

    def test_nonresident_fixed_rate_cases(self):
        commissions = self.env.ref("l10n_ve_withholding_islr.islr_concept_comisiones")
        interest = self.env.ref(
            "l10n_ve_withholding_islr.islr_concept_intereses_inst_financieras"
        )
        bill = self._create_bill(
            self.partner_foreign,
            lines=[
                {"price_unit": 1000.0, "l10n_ve_islr_concept_id": commissions.id},
                {"price_unit": 1000.0, "l10n_ve_islr_concept_id": interest.id},
                {"price_unit": 1000.0},
            ],
        )
        expected = {
            commissions: (5000.0, 5.0, "021"),
            interest: (4950.0, 4.95, "024"),
        }
        for concept, (amount, rate, code) in expected.items():
            with self.subTest(concept=concept.name):
                voucher = self._issued(bill, concept)
                self.assertFalse(voucher.is_tarifa2)
                self.assertAlmostEqual(voucher.base, 100000.0, places=2)
                self.assertAlmostEqual(voucher.taxable_base, 100000.0, places=2)
                self.assertAlmostEqual(voucher.rate, rate, places=2)
                self.assertAlmostEqual(voucher.amount, amount, places=2)
                self.assertEqual(concept._get_seniat_code("pj_nodom"), code)
        # Fixed-rate vouchers do not accumulate for Tarifa N° 2: the line of
        # the Tarifa N° 2 concept starts at 15 %, 30000 Bs x 15 %.
        t2 = self._issued(bill, self.concept_t2)
        self.assertTrue(t2.is_tarifa2)
        self.assertAlmostEqual(t2.amount, 4500.0, places=2)
        self.assertAlmostEqual(
            bill._l10n_ve_islr_get_tarifa2_prior_base(self.concept_t2), 0.0
        )
        self.assertAlmostEqual(bill.amount_residual, 3000.0 - 144.5, places=2)

    def test_treaty_reduced_rate_and_zero(self):
        self.partner_foreign.write(
            {
                "l10n_ve_islr_treaty": True,
                "l10n_ve_islr_treaty_rate": 10.0,
                "l10n_ve_islr_treaty_certificate": "CRF-2026-0001",
            }
        )
        self.assertAlmostEqual(self.partner_foreign.l10n_ve_islr_rate, 10.0)
        # The treaty rate applies to the gross amount, not the 30 % base.
        bill = self._create_bill(self.partner_foreign, 1000.0)
        voucher = self._assert_voucher(bill, 100000.0, 10000.0, concept=self.concept_t2)
        self.assertTrue(voucher.treaty_applied)
        self.assertEqual(voucher.treaty_certificate, "CRF-2026-0001")
        self.assertFalse(voucher.is_tarifa2)
        self.assertAlmostEqual(voucher.base_pct, 100.0, places=2)
        self.assertAlmostEqual(voucher.taxable_base, 100000.0, places=2)
        self.assertAlmostEqual(voucher.rate, 10.0, places=2)
        self._assert_entry(bill, voucher, 100.0)
        # A 0 % treaty still issues the voucher, without an entry.
        self.partner_foreign.l10n_ve_islr_treaty_rate = 0.0
        bill_zero = self._create_bill(self.partner_foreign, 1000.0, ref="FAC-00012400")
        voucher_zero = self._assert_voucher(
            bill_zero, 100000.0, 0.0, concept=self.concept_t2
        )
        self.assertTrue(voucher_zero.treaty_applied)
        self.assertFalse(voucher_zero.wh_move_id)
        self.assertAlmostEqual(bill_zero.amount_residual, 1000.0, places=2)
        details = self._export_xml()
        self.assertEqual(
            {detail.findtext("PorcentajeRetencion") for detail in details},
            {"10.00", "0.00"},
        )
        # A treaty on a resident vendor is ignored.
        self.partner_pj.write(
            {"l10n_ve_islr_treaty": True, "l10n_ve_islr_treaty_rate": 1.0}
        )
        resident = self._assert_voucher(
            self._create_bill(self.partner_pj, 1000.0), 100000.0, 5000.0
        )
        self.assertFalse(resident.treaty_applied)

    def _tarifa2_credit_note_scenario(self, year, credit_note_first):
        # Bill 1: 10000 USD = 1000000 Bs x 30 % = 300000 Bs taxable.
        # Bill 2: 2000 USD = 60000 Bs taxable. Credit note on bill 1:
        # 5000 USD, net taxable 150000 Bs.
        bill_1 = self._create_bill(self.partner_foreign, 10000.0, f"{year}-07-10")
        original = self._assert_t2(bill_1, 300000.0, 52000.0, 17.33)

        def refund():
            return self._create_bill(
                self.partner_foreign,
                5000.0,
                bill_date=f"{year}-07-20",
                ref="NC-00000010",
                move_type="in_refund",
                reversed_entry=bill_1,
            )

        def bill():
            return self._create_bill(
                self.partner_foreign, 2000.0, f"{year}-07-12", ref="FAC-00012500"
            )

        if credit_note_first:
            credit_note = refund()
            bill_2 = bill()
        else:
            bill_2 = bill()
            # 360000 Bs accumulated: 72400 - 52000.
            self._assert_t2(bill_2, 60000.0, 20400.0, 34.0)
            credit_note = refund()
        self.assertEqual(original.state, "cancelled")
        self.assertEqual(original.credit_note_id, credit_note)
        self.assertFalse(credit_note.l10n_ve_islr_voucher_ids)
        # Net 150000 Bs x 15 % = 22500 Bs; bill 2 follows it:
        # 210000 Bs = 30000 + 10000 x 22 % = 32200 - 22500 = 9700 Bs.
        voucher_1 = self._assert_t2(bill_1, 150000.0, 22500.0, 15.0)
        voucher_2 = self._assert_t2(bill_2, 60000.0, 9700.0, 16.17)
        self._assert_entry(bill_1, voucher_1, 225.0)
        self._assert_entry(bill_2, voucher_2, 97.0)
        self.assertAlmostEqual(bill_1.amount_residual, 4775.0, places=2)
        self.assertAlmostEqual(bill_2.amount_residual, 1903.0, places=2)
        self.assertEqual(
            len(bill_2.l10n_ve_islr_voucher_ids), 1 + (not credit_note_first)
        )

    def test_tarifa2_partial_credit_note_same_month(self):
        self._tarifa2_credit_note_scenario("2026", credit_note_first=False)

    def test_tarifa2_credit_note_order_independent(self):
        self._tarifa2_credit_note_scenario("2027", credit_note_first=True)

    def test_tarifa2_backdated_bill_reissues_later_vouchers(self):
        later = self._create_bill(self.partner_foreign, 4000.0, "2026-07-20")
        first = self._assert_t2(later, 120000.0, 18000.0, 15.0)
        earlier = self._create_bill(
            self.partner_foreign, 4000.0, "2026-07-05", ref="FAC-00012600"
        )
        self._assert_t2(earlier, 120000.0, 18000.0, 15.0)
        self.assertEqual(first.state, "cancelled")
        voucher = self._assert_t2(later, 120000.0, 20800.0, 17.33)
        self._assert_entry(later, voucher, 208.0)

    def test_xml_code_per_person_type(self):
        partner_nores = (
            self.env["res.partner"]
            .with_context(no_vat_validation=True)
            .create(
                {
                    "name": "Proveedor PN No Residente",
                    "vat": "V-98765432-1",
                    "email": "pnnr@example.com",
                    "l10n_ve_person_type": "pn_nores",
                    "l10n_ve_islr_concept_id": self.concept.id,
                }
            )
        )
        self.partner_foreign.l10n_ve_islr_concept_id = self.concept
        for partner in (
            self.partner_pj,
            self.partner_pn,
            partner_nores,
            self.partner_foreign,
        ):
            self._create_bill(partner, 1000.0)
        rows = {
            detail.findtext("CodigoConcepto"): (
                detail.findtext("MontoOperacion"),
                detail.findtext("PorcentajeRetencion"),
            )
            for detail in self._export_xml()
        }
        # The amount of the operation is the gross base; Tarifa N° 2 reports
        # its effective rate (90000 Bs taxable x 15 %).
        self.assertEqual(
            rows,
            {
                "004": ("100000.00", "5.00"),
                "002": ("100000.00", "3.00"),
                "003": ("100000.00", "34.00"),
                "005": ("100000.00", "15.00"),
            },
        )

    # Concepts by person type (SENIAT table, Decree 1,808 art. 9)

    def _concept(self, xmlid):
        return self.env.ref(f"l10n_ve_withholding_islr.{xmlid}")

    def _person_type_codes(self, concept):
        return (
            concept.seniat_code_pj,
            concept.seniat_code_pn,
            concept.seniat_code_pn_nores,
            concept.seniat_code_pj_nodom,
        )

    def test_royalties_only_for_non_residents(self):
        royalties = self._concept("islr_concept_canones_regalias")
        self.assertEqual(royalties.name, "Regalías")
        self.assertEqual(
            self._person_type_codes(royalties), ("000", "000", "034", "035")
        )
        self.assertEqual((royalties.rate_pj_dom, royalties.rate_pn_res), (0.0, 0.0))
        self.assertFalse(royalties.apply_subtrahend)
        self.assertAlmostEqual(royalties.rate_pn_nores, 34.0, places=2)
        self.assertAlmostEqual(royalties.base_pct_pn_nores, 90.0, places=2)
        self.assertEqual(royalties.pj_nodom_rate_type, "tarifa2")
        self.assertAlmostEqual(royalties.base_pct_pj_nodom, 90.0, places=2)
        self.assertEqual(royalties.applicable_person_types, "PN No Res., PJ No Dom.")

    def test_international_freight_only_for_non_domiciled(self):
        freight = self._concept("islr_concept_fletes_internacionales")
        self.assertEqual(self._person_type_codes(freight), ("000", "000", "000", "030"))
        self.assertEqual((freight.rate_pj_dom, freight.rate_pn_res), (0.0, 0.0))
        self.assertEqual(freight.pj_nodom_rate_type, "tarifa2")
        self.assertAlmostEqual(freight.base_pct_pj_nodom, 5.0, places=2)
        in_country = self._concept("islr_concept_fletes_internacionales_pais")
        self.assertEqual(
            self._person_type_codes(in_country), ("000", "000", "000", "031")
        )
        self.assertEqual(in_country.pj_nodom_rate_type, "tarifa2")
        self.assertAlmostEqual(in_country.base_pct_pj_nodom, 10.0, places=2)
        self.assertEqual(in_country.applicable_person_types, "PJ No Dom.")

    def test_insurance_premiums_only_for_non_domiciled(self):
        premiums = self._concept("islr_concept_primas_seguro")
        self.assertEqual(
            self._person_type_codes(premiums), ("000", "000", "000", "040")
        )
        self.assertEqual(premiums.rate_pj_dom, 0.0)
        self.assertEqual(premiums.pj_nodom_rate_type, "fixed")
        self.assertAlmostEqual(premiums.rate_pj_nodom, 10.0, places=2)
        self.assertAlmostEqual(premiums.base_pct_pj_nodom, 30.0, places=2)

    def test_public_entities_goods_concept_removed(self):
        # Purchases of goods from domiciled entities are not subject to ISLR
        # withholding, and 080 is goodwill sold by non-resident individuals.
        self.assertFalse(
            self.env.ref(
                "l10n_ve_withholding_islr.islr_concept_adquisicion_bienes_publicos",
                raise_if_not_found=False,
            )
        )
        concepts = (
            self.env["l10n.ve.islr.concept"].with_context(active_test=False).search([])
        )
        self.assertEqual(
            concepts.filtered(lambda c: "080" in self._person_type_codes(c)),
            self._concept("islr_concept_fondos_comercio"),
        )

    def test_in_country_freight_tarifa2_on_10pct_base(self):
        # 1000 USD = 100000 Bs x 10 % = 10000 Bs taxable, first bracket 15 %.
        in_country = self._concept("islr_concept_fletes_internacionales_pais")
        self.partner_foreign.l10n_ve_islr_concept_id = in_country
        bill = self._create_bill(self.partner_foreign, 1000.0)
        voucher = self._issued(bill, in_country)
        self.assertEqual(voucher.person_type, "pj_nodom")
        self.assertTrue(voucher.is_tarifa2)
        self.assertEqual(voucher.seniat_code, "031")
        self.assertAlmostEqual(voucher.base_pct, 10.0, places=2)
        self.assertAlmostEqual(voucher.taxable_base, 10000.0, places=2)
        self.assertAlmostEqual(voucher.rate, 15.0, places=2)
        self.assertAlmostEqual(voucher.amount, 1500.0, places=2)
        self._assert_entry(bill, voucher, 15.0)
        details = self._export_xml()
        self.assertEqual(
            [
                (d.findtext("CodigoConcepto"), d.findtext("PorcentajeRetencion"))
                for d in details
            ],
            [("031", "15.00")],
        )

    def test_non_resident_concept_rejected_on_resident_vendor(self):
        royalties = self._concept("islr_concept_canones_regalias")
        self.partner_pj.l10n_ve_islr_concept_id = royalties
        bill = self._create_bill(self.partner_pj, post=False)
        with self.assertRaises(UserError) as error:
            bill.action_post()
        self.assertIn("Regalías", str(error.exception))
        message = str(error.exception)
        self.assertIn(self.partner_pj.name, message)
        self.assertIn("Persona Jurídica Domiciliada", message)
        self.assertEqual(bill.state, "draft")
        self.assertFalse(bill.l10n_ve_islr_voucher_ids)

    def test_resident_concept_rejected_on_non_resident_vendor(self):
        bill = self._create_bill(
            self.partner_foreign,
            lines=[{"product_id": self.product_freight.id, "price_unit": 1000.0}],
            post=False,
        )
        self.assertEqual(bill.invoice_line_ids.l10n_ve_islr_concept_id, self.concept_2)
        with self.assertRaises(UserError) as error:
            bill.action_post()
        self.assertIn("Fletes de prueba", str(error.exception))
        message = str(error.exception)
        self.assertIn(self.partner_foreign.name, message)
        self.assertIn("Persona Jurídica No Domiciliada", message)
        self.assertEqual(bill.state, "draft")

    def test_applicable_concept_still_withheld_by_type(self):
        # The concept is accepted for the person types it has a code for,
        # and a 0 % treaty still issues the voucher without an entry.
        royalties = self._concept("islr_concept_canones_regalias")
        self.partner_foreign.write(
            {
                "l10n_ve_islr_concept_id": royalties.id,
                "l10n_ve_islr_treaty": True,
                "l10n_ve_islr_treaty_rate": 0.0,
            }
        )
        bill = self._create_bill(self.partner_foreign, 1000.0)
        voucher = self._issued(bill, royalties)
        self.assertEqual(voucher.seniat_code, "035")
        self.assertTrue(voucher.treaty_applied)
        self.assertAlmostEqual(voucher.amount, 0.0, places=2)
        self.assertFalse(voucher.wh_move_id)
        freight = self._create_bill(
            self.partner_pj,
            lines=[{"product_id": self.product_freight.id, "price_unit": 1000.0}],
            ref="FAC-00012346",
        )
        self.assertEqual(self._issued(freight, self.concept_2).seniat_code, "072")

    def test_concept_without_code_blocks_button_and_reissue(self):
        bill = self._create_bill(self.partner_pj, 1000.0)
        voucher = bill.l10n_ve_islr_voucher_ids
        self.assertEqual(voucher.seniat_code, "004")
        # The concept stops applying to domiciled companies after issuing.
        self.concept.seniat_code_pj = "000"
        self.assertEqual(
            self.concept.applicable_person_types, "PN Res., PN No Res., PJ No Dom."
        )
        # The issued voucher keeps its code: re-exporting is not blocked.
        details = self._export_xml()
        self.assertEqual([d.findtext("CodigoConcepto") for d in details], ["004"])
        # A same-month partial credit note would re-issue the net voucher.
        with self.assertRaises(UserError) as error:
            self._create_bill(
                self.partner_pj,
                400.0,
                bill_date="2026-07-25",
                ref="NC-00000002",
                move_type="in_refund",
                reversed_entry=bill,
            )
        self.assertIn("no aplica", str(error.exception))
        self.assertEqual(voucher.state, "issued")
        # Once the voucher is cancelled, the button cannot issue it either.
        voucher.action_cancel()
        self.assertTrue(bill.l10n_ve_islr_wh_pending)
        with self.assertRaises(UserError) as error:
            bill.action_l10n_ve_create_islr_wh()
        self.assertIn("no aplica", str(error.exception))
        self.assertFalse(
            bill.l10n_ve_islr_voucher_ids.filtered(lambda v: v.state == "issued")
        )

    def test_manual_voucher_issue_requires_applicable_concept(self):
        voucher = self.env["l10n.ve.islr.voucher"].create(
            {
                "date": BILL_DATE,
                "partner_id": self.partner_pj.id,
                "concept_id": self._concept("islr_concept_canones_regalias").id,
                "person_type": "pj_dom",
                "base": 100.0,
                "rate": 5.0,
                "amount": 5.0,
            }
        )
        with self.assertRaises(UserError) as error:
            voucher.action_issue()
        self.assertIn("código SENIAT", str(error.exception))
        self.assertEqual(voucher.state, "draft")
        voucher.person_type = "pj_nodom"
        voucher.action_issue()
        self.assertEqual(voucher.state, "issued")
        self.assertEqual(voucher.seniat_code, "035")

    # Credit-note consistency and locked concepts

    def test_credit_note_of_other_vendor_ignored(self):
        # reversed_entry_id is writable: a credit note of vendor B pointed at
        # the bill of vendor A must not cancel or net A's voucher.
        bill = self._create_bill(self.partner_pj, 1000.0)
        voucher = bill.l10n_ve_islr_voucher_ids
        refund = self._create_bill(
            self.partner_pn,
            400.0,
            bill_date="2026-07-25",
            ref="NC-00000009",
            move_type="in_refund",
            reversed_entry=bill,
        )
        self.assertEqual(refund.state, "posted")
        self.assertEqual(refund.reversed_entry_id, bill)
        self.assertEqual(voucher.state, "issued")
        self.assertFalse(voucher.credit_note_id)
        self.assertFalse(bill._l10n_ve_islr_get_netting_credit_notes())
        self.assertFalse(bill.l10n_ve_islr_wh_pending)
        self.assertEqual(
            [d.findtext("MontoOperacion") for d in self._export_xml()],
            ["100000.00"],
        )
        # It adjusted nothing, so it can be reset to draft.
        refund.button_draft()
        self.assertEqual(refund.state, "draft")
        self.assertEqual(voucher.state, "issued")

    def test_concept_locked_on_posted_lines(self):
        user = self._accountant(login="islr_concept_lock")
        bill = self._create_bill(self.partner_pj, 1000.0)
        refund = self._create_bill(
            self.partner_pj,
            400.0,
            bill_date="2026-07-25",
            ref="NC-00000010",
            move_type="in_refund",
            reversed_entry=bill,
        )
        for move in (bill, refund):
            line = move.invoice_line_ids.with_user(user)
            with self.subTest(move=move.move_type):
                for value in (self.concept_2.id, False):
                    with self.assertRaises(UserError):
                        line.write({"l10n_ve_islr_concept_id": value})
                self.assertEqual(
                    move.invoice_line_ids.l10n_ve_islr_concept_id, self.concept
                )
                # Writing the same value is harmless.
                line.write({"l10n_ve_islr_concept_id": self.concept.id})
        draft = self._create_bill(self.partner_pj, ref="FAC-00012399", post=False)
        draft.invoice_line_ids.with_user(user).write(
            {"l10n_ve_islr_concept_id": self.concept_2.id}
        )
        self.assertEqual(draft.invoice_line_ids.l10n_ve_islr_concept_id, self.concept_2)

    def test_voucher_protected_fields_rpc(self):
        # An accounting manager creates and edits manual vouchers, but the
        # state, the links and the module-computed values are not writable.
        user = self._accountant(login="islr_voucher_rpc")
        bill = self._create_bill(self.partner_pj, 1000.0)
        issued = bill.l10n_ve_islr_voucher_ids
        model = self.env["l10n.ve.islr.voucher"].with_user(user)
        vals = {
            "date": BILL_DATE,
            "partner_id": self.partner_pj.id,
            "concept_id": self.concept.id,
            "base": 100.0,
            "rate": 5.0,
            "amount": 5.0,
        }
        forbidden = [
            {"state": "issued"},
            {"source_move_id": bill.id},
            {"wh_move_id": issued.wh_move_id.id},
            {"credit_note_id": bill.id},
            {"seniat_code": "004"},
            {"is_tarifa2": True},
            {"treaty_applied": True},
            {"taxable_base": 1.0},
            {"base_pct": 50.0},
            {"number": "20260799999999"},
        ]
        for extra in forbidden:
            with self.subTest(create=extra), self.assertRaises(UserError):
                model.create(dict(vals, **extra))
        # The neutral values the web client sends on create are accepted.
        voucher = model.create(
            dict(vals, state="draft", base_pct=100.0, is_tarifa2=False)
        )
        self.assertEqual(voucher.state, "draft")
        for extra in forbidden:
            with self.subTest(write=extra), self.assertRaises(UserError):
                voucher.write(extra)
        voucher.write({"base": 200.0, "amount": 10.0})
        voucher.action_issue()
        self.assertEqual(voucher.state, "issued")
        self.assertEqual(voucher.seniat_code, "004")
        self.assertAlmostEqual(voucher.taxable_base, 200.0, places=2)
        self.assertFalse(voucher.source_move_id)

    # Vouchers issued outside the system

    def _external_vals(self, **values):
        return {
            "date": BILL_DATE,
            "partner_id": self.partner_pj.id,
            "concept_id": self.concept.id,
            "base": 100.0,
            "rate": 5.0,
            "amount": 5.0,
            "is_external": True,
            "number": "20260700000777",
            **values,
        }

    def test_external_voucher_registered_and_issued_by_manager(self):
        model = self.env["l10n.ve.islr.voucher"]
        manual = dict(self._external_vals(), is_external=False)
        del manual["number"]
        before = model.create(dict(manual))
        voucher = model.with_user(self._accountant()).create(self._external_vals())
        self.assertEqual(voucher.number, "20260700000777")
        voucher.write({"number": "20260700000778"})
        voucher.action_issue()
        self.assertEqual(voucher.state, "issued")
        self.assertEqual(voucher.number, "20260700000778")
        # The external number did not consume the sequence.
        after = model.create(dict(manual))
        self.assertEqual(int(after.number), int(before.number) + 1)
        for vals in (
            {"number": "20260700000779"},
            {"amount": 1.0},
            {"is_external": False},
            {"state": "draft"},
        ):
            with self.subTest(vals=vals), self.assertRaises(UserError):
                voucher.write(vals)
        voucher.action_cancel()
        with self.assertRaises(UserError):
            voucher.write({"number": "20260700000779"})
        self.assertEqual(voucher.number, "20260700000778")

    def test_external_voucher_number_format_and_unique(self):
        model = self.env["l10n.ve.islr.voucher"].with_user(self._accountant())
        for number in (
            "2026070000077",
            "202607000007777",
            "20261300000001",
            "20260000000001",
            "2026A700000001",
            "20260600000001",
        ):
            with self.subTest(number=number), self.assertRaises(ValidationError):
                model.create(self._external_vals(number=number))
        for number in (False, "", "/"):
            with self.subTest(number=number), self.assertRaises(UserError):
                model.create(self._external_vals(number=number))
        bill = self._create_bill(self.partner_pj)
        existing = bill.l10n_ve_islr_voucher_ids
        with self.assertRaises(ValidationError):
            model.create(self._external_vals(number=existing.number))
        voucher = model.create(self._external_vals())
        with self.assertRaises(ValidationError):
            model.create(self._external_vals())
        with self.assertRaises(ValidationError):
            voucher.write({"number": "20261300000001"})

    def test_external_voucher_requires_manager(self):
        user = new_test_user(
            self.env,
            login="islr_external_invoicing",
            groups="base.group_user,account.group_account_invoice",
            company_id=self.company.id,
            company_ids=[Command.set(self.company.ids)],
        )
        model = self.env["l10n.ve.islr.voucher"]
        with self.assertRaises(AccessError):
            model.with_user(user).create(self._external_vals())
        # Even with create rights granted by another module, only the
        # accounting manager group may supply the number.
        self.env["ir.model.access"].create(
            {
                "name": "test create islr voucher",
                "model_id": self.env.ref(
                    "l10n_ve_withholding_islr.model_l10n_ve_islr_voucher"
                ).id,
                "group_id": self.env.ref("account.group_account_invoice").id,
                "perm_read": True,
                "perm_write": True,
                "perm_create": True,
            }
        )
        with self.assertRaises(AccessError):
            model.with_user(user).create(self._external_vals())
        draft = model.with_user(self._accountant()).create(self._external_vals())
        with self.assertRaises(AccessError):
            draft.with_user(user).write({"number": "20260700000778"})
        self.assertEqual(draft.number, "20260700000777")

    def test_automatic_voucher_number_stays_system_only(self):
        bill = self._create_bill(self.partner_pj)
        voucher = bill.l10n_ve_islr_voucher_ids
        self.assertFalse(voucher.is_external)
        self.assertRegex(voucher.number, r"^202607\d{8}$")
        accountant = self._accountant()
        for vals in ({"number": "20260700000777"}, {"is_external": True}):
            with self.subTest(vals=vals), self.assertRaises(UserError):
                voucher.with_user(accountant).write(vals)
        vals = self._external_vals(is_external=False)
        del vals["number"]
        draft = self.env["l10n.ve.islr.voucher"].create(vals)
        with self.assertRaises(UserError):
            draft.with_user(accountant).write({"number": "20260700000777"})

    # Printed voucher (Decreto 1.808, art. 24)

    def _render_voucher(self, voucher):
        html = self.env["ir.actions.report"]._render_qweb_html(
            "l10n_ve_withholding_islr.report_islr_voucher", voucher.ids
        )[0]
        return " ".join(html.decode().split())

    def test_report_mandatory_content(self):
        bill = self._create_bill(self.partner_pj, ref="FAC-0042")
        voucher = bill.l10n_ve_islr_voucher_ids
        html = self._render_voucher(voucher)
        for text in (
            voucher.number,
            "J-12345678-4",
            "J-98765432-4",
            "pj@example.com",
            "Fecha de Emisión",
            "Fecha de Entrega al Proveedor",
            "____/____/________",
            "N° Control",
            "FAC-0042",
            "Base Imponible",
            "% Retención",
            "Monto Retenido",
            f"{voucher.rate:.2f}",
            voucher.period,
        ):
            with self.subTest(text=text):
                self.assertIn(text, html)
        voucher.write({"delivery_date": "2026-07-20"})
        self.assertNotIn("____/____/________", self._render_voucher(voucher))

    def test_delivery_date_writable_after_issue(self):
        voucher = self._create_bill(self.partner_pj).l10n_ve_islr_voucher_ids
        accountant_voucher = voucher.with_user(self._accountant())
        accountant_voucher.write({"delivery_date": "2026-07-20"})
        self.assertEqual(voucher.delivery_date, fields.Date.to_date("2026-07-20"))
        for vals in (
            {"delivery_date": "2026-07-21", "amount": 1.0},
            {"date": "2026-07-16"},
        ):
            with self.subTest(vals=vals), self.assertRaises(UserError):
                accountant_voucher.write(vals)
        self.assertEqual(voucher.delivery_date, fields.Date.to_date("2026-07-20"))
        voucher.action_cancel()
        accountant_voucher.write({"delivery_date": False})
        self.assertFalse(voucher.delivery_date)

    def test_vendor_without_email_warns_but_does_not_block(self):
        self.partner_pj.email = False
        bill = self._create_bill(self.partner_pj)
        voucher = bill.l10n_ve_islr_voucher_ids
        self.assertEqual(bill.state, "posted")
        self.assertEqual(voucher.state, "issued")
        self.assertTrue(voucher.partner_email_missing)
        self.partner_pj.email = "pj@example.com"
        voucher.invalidate_recordset(["partner_email_missing"])
        self.assertFalse(voucher.partner_email_missing)
