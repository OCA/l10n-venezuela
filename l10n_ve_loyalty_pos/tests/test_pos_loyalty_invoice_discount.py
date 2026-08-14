# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields
from odoo.tests import tagged
from odoo.addons.l10n_ve_seniat.tests.common import L10nVeSeniatCommon


@tagged("post_install", "-at_install")
class TestPosLoyaltyInvoiceGlobalDiscount(L10nVeSeniatCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if "pos.order" not in cls.env:
            return
        cls.partner_ve = cls.env["res.partner"].create(
            {
                "name": "Partner POS loyalty",
                "country_id": cls.env.ref("base.ve").id,
                "vat": "J12345999",
            }
        )
        cls.product = cls.env["product.product"].create(
            {
                "name": "POS Product",
                "list_price": 100.0,
                "available_in_pos": True,
                "taxes_id": [(6, 0, [cls.company_data["default_tax_sale"].id])],
            }
        )
        cls.program = cls.env["loyalty.program"].create(
            {
                "name": "VE POS Discount",
                "program_type": "promotion",
                "applies_on": "current",
                "trigger": "auto",
                "rule_ids": [
                    (
                        0,
                        0,
                        {
                            "minimum_qty": 1,
                        },
                    )
                ],
                "reward_ids": [
                    (
                        0,
                        0,
                        {
                            "reward_type": "discount",
                            "discount": 10,
                            "discount_mode": "percent",
                            "discount_applicability": "order",
                            "required_points": 1,
                        },
                    )
                ],
            }
        )
        cls.reward = cls.program.reward_ids[:1]

    def test_pos_reward_discount_becomes_global_discount_on_invoice(self):
        if "pos.order" not in self.env:
            self.skipTest("point_of_sale not installed")
        PosConfig = self.env["pos.config"]
        config = PosConfig.search([], limit=1)
        if not config:
            self.skipTest("No POS config available")
        if not config.current_session_id:
            config.open_ui()
        session = config.current_session_id
        order = self.env["pos.order"].create(
            {
                "company_id": self.env.company.id,
                "session_id": session.id,
                "partner_id": self.partner_ve.id,
                "amount_tax": 0.0,
                "amount_total": 90.0,
                "amount_paid": 90.0,
                "amount_return": 0.0,
                "lines": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "qty": 1,
                            "price_unit": 100.0,
                            "price_subtotal": 100.0,
                            "price_subtotal_incl": 100.0,
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "product_id": self.reward.discount_line_product_id.id,
                            "qty": 1,
                            "price_unit": -10.0,
                            "price_subtotal": -10.0,
                            "price_subtotal_incl": -10.0,
                            "is_reward_line": True,
                            "reward_id": self.reward.id,
                            "reward_identifier_code": "test-reward",
                            "points_cost": 1,
                        },
                    ),
                ],
            }
        )
        invoice_vals = order._prepare_invoice_vals()
        invoice_vals["invoice_line_ids"] = order._prepare_invoice_lines()
        invoice = order._create_invoice(invoice_vals)
        reward_products = self.reward.discount_line_product_id
        invoice_reward_lines = invoice.invoice_line_ids.filtered(
            lambda line: line.product_id == reward_products
        )
        self.assertFalse(
            invoice_reward_lines,
            "Reward discount product lines must not appear on VE invoices",
        )
        self.assertTrue(invoice.l10n_ve_global_discount_ids)
        self.assertAlmostEqual(
            sum(invoice.l10n_ve_global_discount_ids.mapped("amount")),
            10.0,
            places=2,
        )

    def test_pos_ewallet_spend_becomes_global_discount_on_invoice(self):
        if "pos.order" not in self.env:
            self.skipTest("point_of_sale not installed")
        PosConfig = self.env["pos.config"]
        config = PosConfig.search([], limit=1)
        if not config:
            self.skipTest("No POS config available")
        if not config.current_session_id:
            config.open_ui()
        session = config.current_session_id
        ewallet_program = self.env["loyalty.program"].create(
            {
                "name": "VE Ewallet Spend",
                "program_type": "ewallet",
                "trigger": "auto",
                "applies_on": "future",
                "reward_ids": [
                    (
                        0,
                        0,
                        {
                            "reward_type": "discount",
                            "discount_mode": "per_point",
                            "discount": 1,
                            "discount_applicability": "order",
                            "required_points": 1,
                            "description": "Monedero electrónico",
                        },
                    )
                ],
            }
        )
        reward = ewallet_program.reward_ids[:1]
        order = self.env["pos.order"].create(
            {
                "company_id": self.env.company.id,
                "session_id": session.id,
                "partner_id": self.partner_ve.id,
                "amount_tax": 0.0,
                "amount_total": 70.0,
                "amount_paid": 70.0,
                "amount_return": 0.0,
                "lines": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "qty": 1,
                            "price_unit": 100.0,
                            "price_subtotal": 100.0,
                            "price_subtotal_incl": 100.0,
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "product_id": reward.discount_line_product_id.id,
                            "qty": 1,
                            "price_unit": -30.0,
                            "price_subtotal": -30.0,
                            "price_subtotal_incl": -30.0,
                            "is_reward_line": True,
                            "reward_id": reward.id,
                            "reward_identifier_code": "ewallet-reward",
                            "points_cost": 30,
                        },
                    ),
                ],
            }
        )
        invoice_vals = order._prepare_invoice_vals()
        invoice_vals["invoice_line_ids"] = order._prepare_invoice_lines()
        invoice = order._create_invoice(invoice_vals)
        invoice_reward_lines = invoice.invoice_line_ids.filtered(
            lambda line: line.product_id == reward.discount_line_product_id
        )
        self.assertFalse(
            invoice_reward_lines,
            "Ewallet spend must not create product lines on VE invoices",
        )
        self.assertTrue(invoice.l10n_ve_global_discount_ids)
        self.assertAlmostEqual(
            sum(invoice.l10n_ve_global_discount_ids.mapped("amount")),
            30.0,
            places=2,
        )

    def test_ewallet_refund_credit_converts_to_wallet_currency(self):
        if "pos.order" not in self.env:
            self.skipTest("point_of_sale not installed")
        PosConfig = self.env["pos.config"]
        config = PosConfig.search([], limit=1)
        if not config:
            self.skipTest("No POS config available")
        if not config.current_session_id:
            config.open_ui()
        session = config.current_session_id
        usd = self.env.ref("base.USD")
        company_currency = self.env.company.currency_id
        if usd == company_currency:
            self.skipTest("Company currency is already USD")
        self.env["res.currency.rate"].create(
            {
                "name": "2026-01-01",
                "currency_id": usd.id,
                "company_id": self.env.company.id,
                "rate": 0.002,
            }
        )
        ewallet_program = self.env["loyalty.program"].create(
            {
                "name": "VE Ewallet USD",
                "program_type": "ewallet",
                "trigger": "auto",
                "applies_on": "future",
                "currency_id": usd.id,
                "pos_ok": True,
                "reward_ids": [
                    (
                        0,
                        0,
                        {
                            "reward_type": "discount",
                            "discount_mode": "per_point",
                            "discount": 1,
                            "discount_applicability": "order",
                            "required_points": 1,
                            "description": "Monedero USD",
                        },
                    )
                ],
            }
        )
        ewallet_program.currency_id = usd
        self.env["loyalty.card"].create(
            {
                "program_id": ewallet_program.id,
                "partner_id": self.partner_ve.id,
                "points": 0,
            }
        )
        pay_later = self.env["pos.payment.method"].search(
            [("journal_id", "=", False)], limit=1
        )
        if not pay_later:
            pay_later = self.env["pos.payment.method"].create(
                {
                    "name": "VE Credit",
                    "split_transactions": True,
                }
            )
        refund_amount = 1000.0
        order = self.env["pos.order"].create(
            {
                "company_id": self.env.company.id,
                "session_id": session.id,
                "partner_id": self.partner_ve.id,
                "amount_tax": 0.0,
                "amount_total": -refund_amount,
                "amount_paid": -refund_amount,
                "amount_return": 0.0,
                "lines": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "qty": -1,
                            "price_unit": refund_amount,
                            "price_subtotal": -refund_amount,
                            "price_subtotal_incl": -refund_amount,
                        },
                    )
                ],
            }
        )
        self.env["pos.payment"].create(
            {
                "pos_order_id": order.id,
                "payment_method_id": pay_later.id,
                "amount": -refund_amount,
            }
        )
        expected_points = company_currency._convert(
            refund_amount,
            usd,
            self.env.company,
            order.date_order.date() if order.date_order else fields.Date.context_today(order),
        )
        order._l10n_ve_credit_ewallet_from_pay_later_refund()
        card = self.env["loyalty.card"].search(
            [
                ("program_id", "=", ewallet_program.id),
                ("partner_id", "=", self.partner_ve.id),
            ],
            limit=1,
        )
        self.assertTrue(card)
        self.assertAlmostEqual(card.points, expected_points, places=2)
        self.assertTrue(order.l10n_ve_ewallet_credit_done)

    def test_ewallet_refund_skips_credit_when_original_paid_on_credit(self):
        if "pos.order" not in self.env:
            self.skipTest("point_of_sale not installed")
        PosConfig = self.env["pos.config"]
        config = PosConfig.search([], limit=1)
        if not config:
            self.skipTest("No POS config available")
        if not config.current_session_id:
            config.open_ui()
        session = config.current_session_id
        ewallet_program = self.env["loyalty.program"].create(
            {
                "name": "VE Ewallet Credit Skip",
                "program_type": "ewallet",
                "trigger": "auto",
                "applies_on": "future",
                "pos_ok": True,
                "reward_ids": [
                    (
                        0,
                        0,
                        {
                            "reward_type": "discount",
                            "discount_mode": "per_point",
                            "discount": 1,
                            "discount_applicability": "order",
                            "required_points": 1,
                            "description": "Monedero",
                        },
                    )
                ],
            }
        )
        card = self.env["loyalty.card"].create(
            {
                "program_id": ewallet_program.id,
                "partner_id": self.partner_ve.id,
                "points": 0,
            }
        )
        pay_later = self.env["pos.payment.method"].search(
            [("journal_id", "=", False)], limit=1
        )
        if not pay_later:
            pay_later = self.env["pos.payment.method"].create(
                {
                    "name": "VE Credit",
                    "split_transactions": True,
                }
            )
        sale_amount = 1000.0
        original = self.env["pos.order"].create(
            {
                "company_id": self.env.company.id,
                "session_id": session.id,
                "partner_id": self.partner_ve.id,
                "amount_tax": 0.0,
                "amount_total": sale_amount,
                "amount_paid": sale_amount,
                "amount_return": 0.0,
                "lines": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "qty": 1,
                            "price_unit": sale_amount,
                            "price_subtotal": sale_amount,
                            "price_subtotal_incl": sale_amount,
                        },
                    )
                ],
            }
        )
        self.env["pos.payment"].create(
            {
                "pos_order_id": original.id,
                "payment_method_id": pay_later.id,
                "amount": sale_amount,
            }
        )
        refund = self.env["pos.order"].create(
            {
                "company_id": self.env.company.id,
                "session_id": session.id,
                "partner_id": self.partner_ve.id,
                "amount_tax": 0.0,
                "amount_total": -sale_amount,
                "amount_paid": -sale_amount,
                "amount_return": 0.0,
                "lines": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "qty": -1,
                            "price_unit": sale_amount,
                            "price_subtotal": -sale_amount,
                            "price_subtotal_incl": -sale_amount,
                            "refunded_orderline_id": original.lines[0].id,
                        },
                    )
                ],
            }
        )
        self.env["pos.payment"].create(
            {
                "pos_order_id": refund.id,
                "payment_method_id": pay_later.id,
                "amount": -sale_amount,
            }
        )
        self.assertTrue(refund._l10n_ve_refunded_order_paid_on_credit())
        refund._l10n_ve_credit_ewallet_from_pay_later_refund()
        self.assertAlmostEqual(card.points, 0.0, places=2)
        self.assertFalse(refund.l10n_ve_ewallet_credit_done)

    def test_ewallet_refund_credits_only_non_credit_portion(self):
        if "pos.order" not in self.env:
            self.skipTest("point_of_sale not installed")
        PosConfig = self.env["pos.config"]
        config = PosConfig.search([], limit=1)
        if not config:
            self.skipTest("No POS config available")
        if not config.current_session_id:
            config.open_ui()
        session = config.current_session_id
        ewallet_program = self.env["loyalty.program"].create(
            {
                "name": "VE Ewallet Mixed",
                "program_type": "ewallet",
                "trigger": "auto",
                "applies_on": "future",
                "pos_ok": True,
                "reward_ids": [
                    (
                        0,
                        0,
                        {
                            "reward_type": "discount",
                            "discount_mode": "per_point",
                            "discount": 1,
                            "discount_applicability": "order",
                            "required_points": 1,
                            "description": "Monedero",
                        },
                    )
                ],
            }
        )
        card = self.env["loyalty.card"].create(
            {
                "program_id": ewallet_program.id,
                "partner_id": self.partner_ve.id,
                "points": 0,
            }
        )
        pay_later = self.env["pos.payment.method"].search(
            [("journal_id", "=", False)], limit=1
        )
        if not pay_later:
            pay_later = self.env["pos.payment.method"].create(
                {
                    "name": "VE Credit",
                    "split_transactions": True,
                }
            )
        cash_method = self.env["pos.payment.method"].search(
            [("journal_id", "!=", False)], limit=1
        )
        if not cash_method:
            self.skipTest("No cash/bank POS payment method available")
        sale_amount = 1000.0
        cash_amount = 400.0
        credit_amount = 600.0
        original = self.env["pos.order"].create(
            {
                "company_id": self.env.company.id,
                "session_id": session.id,
                "partner_id": self.partner_ve.id,
                "amount_tax": 0.0,
                "amount_total": sale_amount,
                "amount_paid": sale_amount,
                "amount_return": 0.0,
                "lines": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "qty": 1,
                            "price_unit": sale_amount,
                            "price_subtotal": sale_amount,
                            "price_subtotal_incl": sale_amount,
                        },
                    )
                ],
            }
        )
        self.env["pos.payment"].create(
            {
                "pos_order_id": original.id,
                "payment_method_id": cash_method.id,
                "amount": cash_amount,
            }
        )
        self.env["pos.payment"].create(
            {
                "pos_order_id": original.id,
                "payment_method_id": pay_later.id,
                "amount": credit_amount,
            }
        )
        refund = self.env["pos.order"].create(
            {
                "company_id": self.env.company.id,
                "session_id": session.id,
                "partner_id": self.partner_ve.id,
                "amount_tax": 0.0,
                "amount_total": -sale_amount,
                "amount_paid": -sale_amount,
                "amount_return": 0.0,
                "lines": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "qty": -1,
                            "price_unit": sale_amount,
                            "price_subtotal": -sale_amount,
                            "price_subtotal_incl": -sale_amount,
                            "refunded_orderline_id": original.lines[0].id,
                        },
                    )
                ],
            }
        )
        self.env["pos.payment"].create(
            {
                "pos_order_id": refund.id,
                "payment_method_id": pay_later.id,
                "amount": -sale_amount,
            }
        )
        self.assertFalse(refund._l10n_ve_refunded_order_paid_on_credit())
        self.assertAlmostEqual(
            refund._l10n_ve_get_pay_later_refund_credit_amount(),
            cash_amount,
            places=2,
        )
        refund._l10n_ve_credit_ewallet_from_pay_later_refund()
        self.assertAlmostEqual(card.points, cash_amount, places=2)
        self.assertTrue(refund.l10n_ve_ewallet_credit_done)
        self.assertAlmostEqual(refund.l10n_ve_ewallet_credited_amount, cash_amount, places=2)

