# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import Command, fields
from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import L10nVeSeniatCommon


@tagged("post_install", "-at_install")
class TestVendorCreditDebit(L10nVeSeniatCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.supplier = cls.env["res.partner"].create(
            {
                "name": "Proveedor NC/ND VE",
                "country_id": cls.env.ref("base.ve").id,
                "vat": "J112233445",
                "supplier_rank": 1,
            }
        )
        cls.test_date = fields.Date.today()

    def _create_vendor_bill(self, price_unit=1000.0):
        bill = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": self.supplier.id,
                "invoice_date": self.test_date,
                "ref": "FAC-PROV-001",
                "invoice_line_ids": [
                    Command.create(
                        {
                            "name": "Compra prueba",
                            "quantity": 1.0,
                            "price_unit": price_unit,
                            "account_id": self.company_data[
                                "default_account_expense"
                            ].id,
                            "tax_ids": [
                                Command.set(
                                    [self.company_data["default_tax_purchase"].id]
                                )
                            ],
                        }
                    )
                ],
            }
        )
        bill.action_post()
        return bill

    def _create_debit_note(self, bill, price_unit=500.0):
        wiz = (
            self.env["account.debit.note"]
            .with_context(active_model="account.move", active_ids=bill.ids)
            .create(
                {
                    "date": self.test_date,
                    "reason": "Cargo adicional proveedor",
                    "copy_lines": False,
                }
            )
        )
        wiz.create_debit()
        debit = self.env["account.move"].search(
            [("debit_origin_id", "=", bill.id)], order="id desc", limit=1
        )
        debit.ensure_one()
        debit.write(
            {
                "ref": "ND-PROV-001",
                "invoice_line_ids": [
                    Command.clear(),
                    Command.create(
                        {
                            "name": "Cargo ND",
                            "quantity": 1.0,
                            "price_unit": price_unit,
                            "account_id": self.company_data[
                                "default_account_expense"
                            ].id,
                            "tax_ids": [
                                Command.set(
                                    [self.company_data["default_tax_purchase"].id]
                                )
                            ],
                        }
                    ),
                ],
            }
        )
        debit.action_post()
        bill.invalidate_recordset()
        return debit

    def test_vendor_bill_shows_credit_and_debit_actions(self):
        purchase_journal = self.company_data["default_journal_purchase"]
        purchase_journal.write({"l10n_ve_emission_medium": "free"})
        bill = self._create_vendor_bill()
        self.assertEqual(bill.l10n_ve_journal_emission_medium, "free")
        self.assertFalse(bill.l10n_ve_invoice_original_printed)
        self.assertTrue(bill.l10n_ve_show_credit_note_action)
        self.assertTrue(bill.l10n_ve_show_debit_note_action)
        self.assertTrue(bill._l10n_ve_allows_credit_debit_actions())
        self.assertTrue(bill._l10n_ve_invoice_emitted_for_credit_debit())

    def test_vendor_bill_skips_emission_check_on_reverse(self):
        purchase_journal = self.company_data["default_journal_purchase"]
        purchase_journal.write({"l10n_ve_emission_medium": "free"})
        bill = self._create_vendor_bill()
        bill._l10n_ve_check_credit_debit_allowed()
        bill.action_reverse()

    def test_vendor_debit_note_creation(self):
        bill = self._create_vendor_bill()
        debit = self._create_debit_note(bill)
        self.assertEqual(debit.move_type, "in_invoice")
        self.assertEqual(debit.debit_origin_id, bill)
        self.assertEqual(debit.state, "posted")
        self.assertTrue(bill.l10n_ve_show_debit_note_action)

    def test_vendor_credit_note_creation(self):
        bill = self._create_vendor_bill()
        credit = bill._reverse_moves()
        credit.ensure_one()
        credit.write({"ref": "NC-PROV-001", "invoice_date": self.test_date})
        credit.action_post()
        self.assertEqual(credit.move_type, "in_refund")
        self.assertEqual(credit.reversed_entry_id, bill)
        bill.invalidate_recordset()
        self.assertTrue(bill.l10n_ve_show_credit_note_action)

    def test_vendor_credit_note_allows_different_amount_and_currency(self):
        usd = self.env.ref("base.USD")
        usd.active = True
        bill = self._create_vendor_bill(price_unit=1000.0)
        credit = bill._reverse_moves()
        credit.ensure_one()
        credit.write(
            {
                "ref": "NC-PROV-USD",
                "invoice_date": self.test_date,
                "currency_id": usd.id,
                "invoice_line_ids": [
                    Command.clear(),
                    Command.create(
                        {
                            "name": "Ajuste parcial proveedor",
                            "quantity": 1.0,
                            "price_unit": 25.0,
                            "account_id": self.company_data[
                                "default_account_expense"
                            ].id,
                            "tax_ids": [
                                Command.set(
                                    [self.company_data["default_tax_purchase"].id]
                                )
                            ],
                        }
                    ),
                ],
            }
        )
        credit.action_post()
        self.assertEqual(credit.currency_id, usd)
        self.assertEqual(credit.amount_untaxed, 25.0)
        self.assertEqual(credit.state, "posted")

    def test_vendor_cannot_create_credit_from_debit_note(self):
        bill = self._create_vendor_bill()
        debit = self._create_debit_note(bill)
        with self.assertRaises(UserError):
            debit.action_reverse()

    def test_vendor_credit_note_for_unreversed_debit(self):
        bill = self._create_vendor_bill()
        debit = self._create_debit_note(bill, price_unit=200.0)
        credit = bill._reverse_moves()
        credit.write({"ref": "NC-PROV-FULL", "invoice_date": self.test_date})
        credit.action_post()
        bill.invalidate_recordset()
        self.assertTrue(bill.l10n_ve_show_unreversed_debit_note_alert)
        wizard = self.env["l10n_ve.account.move.debit.credit.wizard"].create(
            {
                "move_id": bill.id,
                "debit_note_ids": [(6, 0, debit.ids)],
                "reason": "Reversión ND proveedor",
            }
        )
        result = wizard.action_create_credit_note()
        debit_credit = self.env["account.move"].browse(result["res_id"])
        self.assertEqual(debit_credit.move_type, "in_refund")
        self.assertEqual(debit_credit.reversed_entry_id, bill)
        self.assertEqual(debit_credit.l10n_ve_debit_note_reversed_ids, debit)
        debit_credit.write({"ref": "NC-PROV-ND", "invoice_date": self.test_date})
        debit_credit.action_post()
        bill.invalidate_recordset()
        self.assertFalse(bill.l10n_ve_show_unreversed_debit_note_alert)
