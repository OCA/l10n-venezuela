from odoo import fields
from odoo.tests import tagged

from .common import TestPosPaymentCurrencyCommon


@tagged("post_install", "-at_install", "currency_pos")
class TestPosSessionMulticurrency(TestPosPaymentCurrencyCommon):
    def test_session_payment_amount_in_method_currency(self):
        self.multi_currency_config.open_ui()
        session = self.multi_currency_config.current_session_id
        order = self.env["pos.order"].create(
            {
                "session_id": session.id,
                "partner_id": self.partner1.id,
                "amount_total": 100.0,
                "amount_tax": 0.0,
                "amount_paid": 0.0,
                "amount_return": 0.0,
                "last_order_preparation_change": "{}",
            }
        )
        payment = self.env["pos.payment"].create(
            {
                "pos_order_id": order.id,
                "amount": 0.0,
                "payment_method_id": self.eur_bank_payment_method.id,
                "payment_currency_id": self.eur_currency.id,
                "payment_currency_amount": 50.0,
            }
        )
        amount_currency, currency = session._oca_amount_in_payment_method_currency(
            payment,
            self.eur_bank_payment_method,
        )
        self.assertEqual(currency, self.eur_currency)
        self.assertEqual(amount_currency, 50.0)
        self.assertGreater(payment.amount, 0.0)

    def test_nested_payment_create_persists_foreign_amount(self):
        order = self._create_paid_order()
        payment = self.env["pos.payment"].create(
            {
                "amount": 0.0,
                "payment_method_id": self.eur_bank_payment_method.id,
                "payment_currency_amount": 25.0,
                "payment_currency_id": self.eur_currency.id,
                "pos_order_id": order.id,
            }
        )
        self.assertEqual(payment.payment_currency_id, self.eur_currency)
        self.assertEqual(payment.payment_currency_amount, 25.0)
        self.assertGreater(payment.amount, 0.0)

    def test_closing_control_data_shows_foreign_currency(self):
        self.multi_currency_config.open_ui()
        session = self.multi_currency_config.current_session_id
        order = self.env["pos.order"].create(
            {
                "session_id": session.id,
                "partner_id": self.partner1.id,
                "amount_total": 100.0,
                "amount_tax": 0.0,
                "amount_paid": 100.0,
                "amount_return": 0.0,
                "state": "paid",
                "last_order_preparation_change": "{}",
            }
        )
        self.env["pos.payment"].create(
            {
                "pos_order_id": order.id,
                "amount": 0.0,
                "payment_method_id": self.eur_bank_payment_method.id,
                "payment_currency_id": self.eur_currency.id,
                "payment_currency_amount": 40.0,
            }
        )
        closing_data = session.get_closing_control_data()
        eur_method = next(
            item
            for item in closing_data["non_cash_payment_methods"]
            if item["id"] == self.eur_bank_payment_method.id
        )
        self.assertTrue(eur_method["has_foreign_currency"])
        self.assertEqual(eur_method["amount_payment_currency"], 40.0)

    def test_closing_expected_matches_payment_currency_amount(self):
        self.multi_currency_config.open_ui()
        session = self.multi_currency_config.current_session_id
        order = self.env["pos.order"].create(
            {
                "session_id": session.id,
                "partner_id": self.partner1.id,
                "amount_total": 100.0,
                "amount_tax": 0.0,
                "amount_paid": 100.0,
                "amount_return": 0.0,
                "state": "paid",
                "last_order_preparation_change": "{}",
            }
        )
        payment = self.env["pos.payment"].create(
            {
                "pos_order_id": order.id,
                "amount": 0.0,
                "payment_method_id": self.eur_bank_payment_method.id,
                "payment_currency_id": self.eur_currency.id,
                "payment_currency_amount": 50.0,
            }
        )
        self.assertGreater(payment.amount, 0.0)
        closing_data = session.get_closing_control_data()
        eur_method = next(
            item
            for item in closing_data["non_cash_payment_methods"]
            if item["id"] == self.eur_bank_payment_method.id
        )
        self.assertEqual(eur_method["amount_payment_currency"], 50.0)
        self.assertAlmostEqual(eur_method["amount"], payment.amount, places=2)

    def test_cash_change_only_in_order_currency(self):
        order = self._create_paid_order()
        payment = self.env["pos.payment"].create(
            {
                "pos_order_id": order.id,
                "amount": -5.0,
                "payment_method_id": self.cash_payment_method.id,
                "is_change": True,
                "payment_currency_amount": -5.0,
                "payment_currency_id": self.usd_currency.id,
            }
        )
        self.assertEqual(payment.currency_id, self.usd_currency)
        self.assertEqual(payment.payment_currency_id, self.usd_currency)

    def test_usd_overpay_change_in_foreign_currency(self):
        """Pay more in USD, then register change as a negative foreign cash payment."""
        self.multi_currency_config.open_ui()
        session = self.multi_currency_config.current_session_id
        order = self.env["pos.order"].create(
            {
                "session_id": session.id,
                "partner_id": self.partner1.id,
                "amount_total": 80.0,
                "amount_tax": 0.0,
                "amount_paid": 0.0,
                "amount_return": 0.0,
                "last_order_preparation_change": "{}",
            }
        )
        self.env["pos.payment"].create(
            {
                "pos_order_id": order.id,
                "amount": 100.0,
                "payment_method_id": self.cash_payment_method.id,
                "payment_currency_amount": 100.0,
                "payment_currency_id": self.usd_currency.id,
            }
        )
        # Remaining in order currency: -20 USD. Change in EUR (rate 2) => -40 EUR.
        change_foreign_amount = self.env["pos.payment"]._oca_convert_amount(
            -20.0,
            self.usd_currency,
            self.eur_currency,
            self.env.company,
            fields.Date.today(),
        )
        self.assertAlmostEqual(change_foreign_amount, -40.0, places=2)
        change_payment = self.env["pos.payment"].create(
            {
                "pos_order_id": order.id,
                "amount": 0.0,
                "payment_method_id": self.eur_cash_payment_method.id,
                "payment_currency_id": self.eur_currency.id,
                "payment_currency_amount": change_foreign_amount,
                "is_change": True,
            }
        )
        self.assertEqual(change_payment.payment_currency_id, self.eur_currency)
        self.assertAlmostEqual(change_payment.payment_currency_amount, -40.0, places=2)
        self.assertLess(change_payment.amount, 0.0)
        self.assertAlmostEqual(change_payment.amount, -20.0, places=2)
        paid = sum(order.payment_ids.mapped("amount"))
        self.assertAlmostEqual(paid, 80.0, places=2)

    def test_session_close_with_foreign_bank_payment(self):
        self.config = self.multi_currency_config
        session = self.open_new_session(0)
        order_data = self.create_ui_order_data(
            [(self.product_mc, 1)],
            payments=[(self.eur_bank_payment_method, 100.0)],
        )
        self.env["pos.order"].sync_from_ui([order_data])
        payment = session.order_ids.payment_ids.filtered(
            lambda pay: pay.payment_method_id == self.eur_bank_payment_method
        )
        self.assertEqual(len(payment), 1)
        self.assertEqual(payment.payment_currency_id, self.eur_currency)
        self.assertGreater(payment.payment_currency_amount, 0.0)
        session.action_pos_session_closing_control()
        self.assertEqual(session.state, "closed")

    def test_opening_creates_cash_boxes_per_cash_method(self):
        self.config = self.multi_currency_config
        session = self.open_new_session(10)
        self.assertEqual(len(session.cash_box_ids), 2)
        primary_box = session.cash_box_ids.filtered(
            lambda box: box.payment_method_id == self.cash_payment_method
        )
        eur_box = session.cash_box_ids.filtered(
            lambda box: box.payment_method_id == self.eur_cash_payment_method
        )
        self.assertEqual(len(primary_box), 1)
        self.assertEqual(len(eur_box), 1)
        self.assertAlmostEqual(primary_box.balance_start, 10.0, places=2)
        self.assertEqual(eur_box.currency_id, self.eur_currency)

    def test_closing_expected_includes_opening_amounts(self):
        self.config = self.multi_currency_config
        self.multi_currency_config.open_ui()
        session = self.multi_currency_config.current_session_id
        session.oca_set_opening_control(
            {
                self.cash_payment_method.id: 5.0,
                self.eur_cash_payment_method.id: 20.0,
            },
            "multi opening",
        )
        closing_data = session.get_closing_control_data()
        primary = next(
            item
            for item in closing_data["cash_details"]
            if item["id"] == self.cash_payment_method.id
        )
        eur_cash = next(
            item
            for item in closing_data["cash_details"]
            if item["id"] == self.eur_cash_payment_method.id
        )
        self.assertAlmostEqual(primary["opening"], 5.0, places=2)
        self.assertAlmostEqual(primary["amount"], 5.0, places=2)
        self.assertAlmostEqual(eur_cash["opening"], 20.0, places=2)
        self.assertAlmostEqual(eur_cash["amount"], 20.0, places=2)
        self.assertAlmostEqual(eur_cash["amount"] - 0.0, 20.0, places=2)

    def test_next_session_suggests_previous_cash_box_balances(self):
        self.config = self.multi_currency_config
        self.multi_currency_config.open_ui()
        first_session = self.multi_currency_config.current_session_id
        first_session.oca_set_opening_control(
            {
                self.cash_payment_method.id: 5.0,
                self.eur_cash_payment_method.id: 20.0,
            },
            False,
        )
        first_session.post_closing_cash_details(
            5.0,
            counted_cash_by_method={
                self.cash_payment_method.id: 5.0,
                self.eur_cash_payment_method.id: 20.0,
            },
        )
        first_session.close_session_from_ui()
        self.assertEqual(first_session.state, "closed")

        self.multi_currency_config.open_ui()
        second_session = self.multi_currency_config.current_session_id
        openings = second_session._oca_get_cash_box_opening_map()
        self.assertAlmostEqual(openings[self.cash_payment_method.id], 5.0, places=2)
        self.assertAlmostEqual(openings[self.eur_cash_payment_method.id], 20.0, places=2)
        loaded = second_session._load_pos_data({})
        self.assertIn("_oca_cash_box_openings", loaded["data"][0])
        self.assertNotIn("_rt_cash_box_openings", loaded["data"][0])
        self.assertNotIn("rt_cash_box_openings", loaded["data"][0])
        self.assertAlmostEqual(
            loaded["data"][0]["_oca_cash_box_openings"][self.cash_payment_method.id],
            5.0,
            places=2,
        )
        self.assertAlmostEqual(
            loaded["data"][0]["_oca_cash_box_openings"][self.eur_cash_payment_method.id],
            20.0,
            places=2,
        )

    def test_cash_in_out_on_foreign_cash_method(self):
        self.config = self.multi_currency_config
        session = self.open_new_session(0)
        session.try_cash_in_out(
            "in",
            20.0,
            "Float EUR",
            {
                "translatedType": "in",
                "formattedAmount": "20.00",
                "payment_method_id": self.eur_cash_payment_method.id,
            },
        )
        move = session.statement_line_ids.filtered(
            lambda line: line.journal_id == self.eur_cash_journal
        )
        self.assertEqual(len(move), 1)
        self.assertAlmostEqual(move.amount, 20.0, places=2)

    def test_foreign_cash_out_does_not_create_usd_difference(self):
        """Cash out on foreign journal must not post a primary (USD) cash difference.

        Reproduces POS/00017: opened/closed USD at 5.00 with a VES/EUR cash-out
        incorrectly shifted the primary expected balance and booked a fake profit.
        """
        self.config = self.multi_currency_config
        self.multi_currency_config.open_ui()
        session = self.multi_currency_config.current_session_id
        session.oca_set_opening_control(
            {
                self.cash_payment_method.id: 5.0,
                self.eur_cash_payment_method.id: 1010.0,
            },
            False,
        )
        session.try_cash_in_out(
            "out",
            1000.0,
            "SOBRANTE",
            {
                "translatedType": "out",
                "formattedAmount": "1000.00",
                "payment_method_id": self.eur_cash_payment_method.id,
            },
        )
        session.post_closing_cash_details(
            5.0,
            counted_cash_by_method={
                self.cash_payment_method.id: 5.0,
                self.eur_cash_payment_method.id: 10.0,
            },
        )
        primary_box = session._oca_get_cash_box(self.cash_payment_method)
        eur_box = session._oca_get_cash_box(self.eur_cash_payment_method)
        self.assertAlmostEqual(primary_box.closing_difference, 0.0, places=2)
        self.assertAlmostEqual(eur_box.closing_difference, 0.0, places=2)
        self.assertAlmostEqual(session.cash_register_difference, 0.0, places=2)

        session.close_session_from_ui()
        self.assertEqual(session.state, "closed")
        self.assertAlmostEqual(session.cash_real_transaction, 0.0, places=2)

        primary_journal = self.cash_payment_method.journal_id
        usd_statement_lines = session.statement_line_ids.filtered(
            lambda line: line.journal_id == primary_journal
        )
        self.assertFalse(
            usd_statement_lines,
            "No USD cash difference statement line should be created",
        )
        eur_statement_lines = session.statement_line_ids.filtered(
            lambda line: line.journal_id == self.eur_cash_journal
        )
        self.assertEqual(len(eur_statement_lines), 1)
        self.assertAlmostEqual(eur_statement_lines.amount, -1000.0, places=2)

        usd_gain_moves = self.env["account.move.line"].search(
            [
                ("move_id", "in", session.statement_line_ids.move_id.ids),
                ("journal_id", "=", primary_journal.id),
            ]
        )
        self.assertFalse(usd_gain_moves)

    def test_closing_control_lists_all_cash_methods(self):
        self.config = self.multi_currency_config
        session = self.open_new_session(0)
        order_data = self.create_ui_order_data(
            [(self.product_mc, 1)],
            payments=[(self.eur_cash_payment_method, 100.0)],
        )
        self.env["pos.order"].sync_from_ui([order_data])
        payment = session.order_ids.payment_ids.filtered(
            lambda pay: pay.payment_method_id == self.eur_cash_payment_method
        )
        self.assertEqual(payment.payment_currency_id, self.eur_currency)
        closing_data = session.get_closing_control_data()
        self.assertEqual(len(closing_data["cash_details"]), 2)
        eur_cash = next(
            item
            for item in closing_data["cash_details"]
            if item["id"] == self.eur_cash_payment_method.id
        )
        self.assertTrue(eur_cash["has_foreign_currency"])
        self.assertAlmostEqual(
            eur_cash["amount_payment_currency"],
            payment.payment_currency_amount,
            places=2,
        )
        cash_ids = {item["id"] for item in closing_data["cash_details"]}
        non_cash_ids = {item["id"] for item in closing_data["non_cash_payment_methods"]}
        self.assertIn(self.eur_cash_payment_method.id, cash_ids)
        self.assertNotIn(self.eur_cash_payment_method.id, non_cash_ids)

    def test_session_close_with_foreign_cash_payment(self):
        self.config = self.multi_currency_config
        session = self.open_new_session(0)
        order_data = self.create_ui_order_data(
            [(self.product_mc, 1)],
            payments=[(self.eur_cash_payment_method, 100.0)],
        )
        self.env["pos.order"].sync_from_ui([order_data])
        payment = session.order_ids.payment_ids.filtered(
            lambda pay: pay.payment_method_id == self.eur_cash_payment_method
        )
        closing_data = session.get_closing_control_data()
        eur_cash = next(
            item
            for item in closing_data["cash_details"]
            if item["id"] == self.eur_cash_payment_method.id
        )
        counted_map = {
            self.cash_payment_method.id: 0.0,
            self.eur_cash_payment_method.id: eur_cash["amount"],
        }
        session.post_closing_cash_details(
            counted_map[self.cash_payment_method.id],
            counted_cash_by_method=counted_map,
        )
        session.close_session_from_ui()
        self.assertEqual(session.state, "closed")
        eur_box = session.cash_box_ids.filtered(
            lambda box: box.payment_method_id == self.eur_cash_payment_method
        )
        self.assertAlmostEqual(
            eur_box.balance_end_real,
            payment.payment_currency_amount,
            places=2,
        )

    def _create_paid_order(self):
        self.multi_currency_config.open_ui()
        session = self.multi_currency_config.current_session_id
        return self.env["pos.order"].create(
            {
                "session_id": session.id,
                "partner_id": self.partner1.id,
                "amount_total": 100.0,
                "amount_tax": 0.0,
                "amount_paid": 100.0,
                "amount_return": 0.0,
                "state": "paid",
                "last_order_preparation_change": "{}",
            }
        )
