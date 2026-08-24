from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tools import float_compare

from .common import TestPosPaymentCurrencyCommon


@tagged("post_install", "-at_install", "currency_pos")
class TestPosPaymentCurrency(TestPosPaymentCurrencyCommon):
    def test_config_allows_foreign_payment_method(self):
        self.assertTrue(self.multi_currency_config.allow_multi_currency_payment)
        self.assertEqual(
            self.eur_bank_payment_method.payment_currency_id,
            self.eur_currency,
        )

    def test_config_blocks_without_flag(self):
        config = self.env["pos.config"].create(
            {
                "name": "POS Single Currency",
                "journal_id": self.company_data["default_journal_sale"].id,
                "invoice_journal_id": self.company_data["default_journal_sale"].id,
                "allow_multi_currency_payment": False,
            }
        )
        with self.assertRaises(ValidationError):
            config.write({"payment_method_ids": [(4, self.eur_bank_payment_method.id)]})

    def test_payment_conversion_stores_rate(self):
        order = self._create_draft_order()
        payment = self.env["pos.payment"].create(
            {
                "pos_order_id": order.id,
                "amount": 0.0,
                "payment_method_id": self.eur_bank_payment_method.id,
                "payment_currency_id": self.eur_currency.id,
                "payment_currency_amount": 50.0,
            }
        )
        self.assertEqual(payment.payment_currency_id, self.eur_currency)
        self.assertEqual(payment.payment_currency_amount, 50.0)
        self.assertGreater(payment.payment_currency_rate, 0.0)
        self.assertGreater(payment.amount, 0.0)

    def test_order_paid_with_mixed_currencies(self):
        order = self._create_draft_order(amount_total=100.0)
        self.env["pos.payment"].create(
            {
                "pos_order_id": order.id,
                "amount": 40.0,
                "payment_method_id": self.cash_payment_method.id,
                "payment_currency_amount": 40.0,
                "payment_currency_id": self.usd_currency.id,
            }
        )
        self.env["pos.payment"].create(
            {
                "pos_order_id": order.id,
                "amount": 0.0,
                "payment_method_id": self.eur_bank_payment_method.id,
                "payment_currency_id": self.eur_currency.id,
                "payment_currency_amount": 30.0,
            }
        )
        expected_foreign_total = self.env["pos.payment"]._oca_convert_amount(
            30.0,
            self.eur_currency,
            self.usd_currency,
            self.env.company,
            fields.Date.today(),
        )
        paid = sum(order.payment_ids.mapped("amount"))
        self.assertEqual(
            float_compare(
                paid,
                40.0 + expected_foreign_total,
                precision_rounding=self.usd_currency.rounding,
            ),
            0,
        )

    def test_payment_constraint_same_currency(self):
        order = self._create_draft_order(amount_total=10.0)
        payment = self.env["pos.payment"].create(
            {
                "pos_order_id": order.id,
                "amount": 10.0,
                "payment_method_id": self.cash_payment_method.id,
                "payment_currency_id": self.usd_currency.id,
                "payment_currency_amount": 10.0,
            }
        )
        with self.assertRaises(ValidationError):
            payment.write({"payment_currency_amount": 9.0})

    def test_keeps_ui_amount_when_pos_sends_both_amounts(self):
        order = self._create_draft_order(amount_total=35615.69)
        converted = self.env["pos.payment"]._oca_convert_amount(
            48.31,
            self.eur_currency,
            self.usd_currency,
            self.env.company,
            fields.Date.today(),
        )
        ui_amount = self.usd_currency.round(converted + self.usd_currency.rounding)
        self.assertNotEqual(ui_amount, converted)
        payment = self.env["pos.payment"].create(
            {
                "pos_order_id": order.id,
                "amount": ui_amount,
                "payment_method_id": self.eur_bank_payment_method.id,
                "payment_currency_id": self.eur_currency.id,
                "payment_currency_amount": 48.31,
            }
        )
        self.assertEqual(payment.amount, ui_amount)
        self.assertEqual(payment.payment_currency_amount, 48.31)

    def test_absorb_foreign_payment_rounding_on_order(self):
        order = self._create_draft_order(amount_total=100.01)
        payment = self.env["pos.payment"].create(
            {
                "pos_order_id": order.id,
                "amount": 100.0,
                "payment_method_id": self.eur_bank_payment_method.id,
                "payment_currency_id": self.eur_currency.id,
                "payment_currency_amount": 50.0,
            }
        )
        order.amount_paid = payment.amount
        order._oca_absorb_foreign_payment_rounding()
        self.assertEqual(order.amount_paid, 100.01)
        self.assertEqual(payment.amount, 100.01)

    def _create_draft_order(self, amount_total=100.0):
        self.multi_currency_config.open_ui()
        session = self.multi_currency_config.current_session_id
        return self.env["pos.order"].create(
            {
                "session_id": session.id,
                "partner_id": self.partner1.id,
                "amount_total": amount_total,
                "amount_tax": 0.0,
                "amount_paid": 0.0,
                "amount_return": 0.0,
                "last_order_preparation_change": "{}",
            }
        )

    def _create_paid_order(self):
        order = self._create_draft_order()
        self.env["pos.payment"].create(
            {
                "pos_order_id": order.id,
                "amount": 100.0,
                "payment_method_id": self.cash_payment_method.id,
                "payment_currency_amount": 100.0,
                "payment_currency_id": self.usd_currency.id,
            }
        )
        order.amount_paid = 100.0
        order.state = "paid"
        return order
