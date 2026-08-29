# Copyright 2026 BWEALTHICS LLC
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from odoo.addons.point_of_sale.tests.common import CommonPosTest


@tagged("post_install", "-at_install")
class TestPosBs(CommonPosTest):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ves = cls.env.ref("base.VES")
        cls.ves.active = True
        cls.bank_payment_method.write(
            {
                "l10n_ve_require_reference": True,
                "l10n_ve_ves_tender": True,
            }
        )
        cls.split_payment_method = cls.bank_payment_method.copy(
            {
                "name": "Split VES",
                "split_transactions": True,
            }
        )
        cls.pos_config_usd.payment_method_ids += cls.split_payment_method

    def _create_order(self, payment_method=None, amount=10, amount_ves=1000, ref="1"):
        payment_method = payment_method or self.bank_payment_method
        order, _refund = self.create_backend_pos_order(
            {
                "line_data": [
                    {
                        "product_id": self.ten_dollars_no_tax.product_variant_id.id,
                    }
                ],
                "order_data": {"partner_id": self.partner_mobt.id},
            }
        )
        payment = self.env["pos.payment"].create(
            {
                "amount": amount,
                "l10n_ve_amount_ves": amount_ves,
                "l10n_ve_pos_amount": amount,
                "l10n_ve_ves_rate": abs(amount_ves / amount),
                "payment_date": fields.Datetime.now(),
                "payment_method_id": payment_method.id,
                "payment_ref_no": ref,
                "pos_order_id": order.id,
            }
        )
        order.state = "paid"
        return order, payment

    def test_payment_capture_is_required(self):
        order, _refund = self.create_backend_pos_order(
            {
                "line_data": [
                    {
                        "product_id": self.ten_dollars_no_tax.product_variant_id.id,
                    }
                ]
            }
        )
        values = {
            "amount": 10,
            "payment_date": fields.Datetime.now(),
            "payment_method_id": self.bank_payment_method.id,
            "pos_order_id": order.id,
        }
        with self.assertRaisesRegex(ValidationError, "exact VES amount"):
            self.env["pos.payment"].create(values)
        with self.assertRaisesRegex(ValidationError, "same sign"):
            self.env["pos.payment"].create(
                {
                    **values,
                    "l10n_ve_amount_ves": -1000,
                    "l10n_ve_pos_amount": 10,
                    "l10n_ve_ves_rate": 100,
                    "payment_ref_no": "1",
                }
            )
        with self.assertRaisesRegex(ValidationError, "transaction reference"):
            self.env["pos.payment"].create(
                {
                    **values,
                    "l10n_ve_amount_ves": 1000,
                    "l10n_ve_pos_amount": 10,
                    "l10n_ve_ves_rate": 100,
                }
            )
        with self.assertRaisesRegex(ValidationError, "zero POS payment"):
            self.env["pos.payment"].create(
                {
                    **values,
                    "amount": 0,
                    "l10n_ve_amount_ves": 1000,
                    "l10n_ve_ves_rate": 100,
                    "payment_ref_no": "1",
                }
            )

    def test_combined_payment_liquidity_is_in_ves(self):
        order, _payment = self._create_order(ref="ABC-123")
        session = order.session_id

        session.action_pos_session_closing_control()

        account_payment = self.env["account.payment"].search(
            [
                ("pos_session_id", "=", session.id),
                ("pos_payment_method_id", "=", self.bank_payment_method.id),
            ],
            limit=1,
        )
        liquidity_line = account_payment.move_id.line_ids.filtered(
            lambda line: line.account_id == account_payment.outstanding_account_id
        )
        self.assertEqual(liquidity_line.currency_id, self.ves)
        self.assertEqual(liquidity_line.amount_currency, 1000)
        self.assertEqual(liquidity_line.balance, 10)
        self.assertIn("ABC-123", account_payment.move_id.ref)

    def test_split_payments_keep_individual_ves_amounts(self):
        first_order, _payment = self._create_order(
            self.split_payment_method, amount_ves=1000, ref="A"
        )
        self._create_order(self.split_payment_method, amount_ves=1200, ref="B")
        session = first_order.session_id

        session.action_pos_session_closing_control()

        account_payments = self.env["account.payment"].search(
            [
                ("pos_session_id", "=", session.id),
                ("pos_payment_method_id", "=", self.split_payment_method.id),
            ]
        )
        self.assertEqual(len(account_payments), 2)
        amounts_ves = sorted(
            account_payments.move_id.line_ids.filtered(
                lambda line: line.account_id in account_payments.outstanding_account_id
            ).mapped("amount_currency")
        )
        self.assertEqual(amounts_ves, [1000, 1200])

    def test_split_payment_difference_is_rejected(self):
        order, _payment = self._create_order(self.split_payment_method)
        with self.assertRaisesRegex(UserError, "payment difference"):
            order.session_id.action_pos_session_closing_control(
                bank_payment_method_diffs={self.split_payment_method.id: 1}
            )

    def test_refund_capture_uses_negative_ves(self):
        _order, payment = self._create_order(amount=-10, amount_ves=-1000)
        self.assertEqual(payment.l10n_ve_amount_ves, -1000)
