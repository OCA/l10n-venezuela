from odoo.tests import tagged

from .common import TestPosPaymentCurrencyCommon


@tagged("post_install", "-at_install", "currency_pos")
class TestPosPaymentMethodLines(TestPosPaymentCurrencyCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Account = cls.env["account.account"]
        cls.outstanding_receipts = Account.create(
            {
                "name": "Outstanding Receipts POS",
                "code": "RTPR01",
                "account_type": "asset_current",
                "reconcile": True,
            }
        )
        cls.outstanding_payments = Account.create(
            {
                "name": "Outstanding Payments POS",
                "code": "RTPP01",
                "account_type": "asset_current",
                "reconcile": True,
            }
        )
        inbound = cls.eur_cash_journal.inbound_payment_method_line_ids[:1]
        outbound = cls.eur_cash_journal.outbound_payment_method_line_ids[:1]
        inbound.payment_account_id = cls.outstanding_receipts
        outbound.payment_account_id = cls.outstanding_payments
        cls.eur_cash_inbound_line = inbound
        cls.eur_cash_outbound_line = outbound
        cls.eur_cash_payment_method.write(
            {
                "inbound_payment_method_line_id": inbound.id,
                "outbound_payment_method_line_id": outbound.id,
            }
        )

    def test_defaults_from_journal_payment_method_lines(self):
        method = self.env["pos.payment.method"].create(
            {
                "name": "Cash EUR Defaults",
                "journal_id": self.eur_cash_journal.id,
                "receivable_account_id": self.company_data["default_account_receivable"].id,
            }
        )
        self.assertEqual(method.inbound_payment_method_line_id, self.eur_cash_inbound_line)
        self.assertEqual(method.outbound_payment_method_line_id, self.eur_cash_outbound_line)
        self.assertEqual(method.inbound_payment_account_id, self.outstanding_receipts)
        self.assertEqual(method.outbound_payment_account_id, self.outstanding_payments)

    def test_journal_change_resets_payment_method_lines(self):
        other_cash = self.env["account.journal"].create(
            {
                "name": "Other Cash POS",
                "type": "cash",
                "code": "OCSH",
            }
        )
        method = self.env["pos.payment.method"].create(
            {
                "name": "Cash Switch Journal",
                "journal_id": self.eur_cash_journal.id,
                "receivable_account_id": self.company_data["default_account_receivable"].id,
            }
        )
        self.assertEqual(method.inbound_payment_method_line_id.journal_id, self.eur_cash_journal)
        method.journal_id = other_cash
        self.assertEqual(method.inbound_payment_method_line_id.journal_id, other_cash)
        self.assertEqual(method.outbound_payment_method_line_id.journal_id, other_cash)

    def _assert_counterpart_account(self, statement_line, expected_account):
        counterpart_lines = statement_line.move_id.line_ids.filtered(
            lambda line: line.account_id == expected_account
        )
        self.assertTrue(
            counterpart_lines,
            "Expected counterpart account %s on statement move" % expected_account.display_name,
        )

    def test_cash_in_uses_inbound_outstanding_account(self):
        self.config = self.multi_currency_config
        session = self.open_new_session(0)
        session.try_cash_in_out(
            "in",
            15.0,
            "Float inbound",
            {
                "translatedType": "in",
                "formattedAmount": "15.00",
                "payment_method_id": self.eur_cash_payment_method.id,
            },
        )
        move = session.statement_line_ids.filtered(
            lambda line: line.journal_id == self.eur_cash_journal and line.amount > 0
        )
        self.assertEqual(len(move), 1)
        self._assert_counterpart_account(move, self.outstanding_receipts)

    def test_cash_out_uses_outbound_outstanding_account(self):
        self.config = self.multi_currency_config
        session = self.open_new_session(0)
        session.try_cash_in_out(
            "out",
            12.0,
            "Cash out outbound",
            {
                "translatedType": "out",
                "formattedAmount": "12.00",
                "payment_method_id": self.eur_cash_payment_method.id,
            },
        )
        move = session.statement_line_ids.filtered(
            lambda line: line.journal_id == self.eur_cash_journal and line.amount < 0
        )
        self.assertEqual(len(move), 1)
        self._assert_counterpart_account(move, self.outstanding_payments)

    def test_cash_in_without_line_uses_suspense(self):
        suspense_journal = self.env["account.journal"].create(
            {
                "name": "Suspense Cash POS",
                "type": "cash",
                "code": "SCSH",
                "currency_id": self.eur_currency.id,
            }
        )
        suspense_journal.write(
            {
                "inbound_payment_method_line_ids": [(5, 0, 0)],
                "outbound_payment_method_line_ids": [(5, 0, 0)],
            }
        )
        method = self.env["pos.payment.method"].create(
            {
                "name": "Cash No Lines",
                "journal_id": suspense_journal.id,
                "receivable_account_id": self.company_data["default_account_receivable"].id,
            }
        )
        method.write(
            {
                "inbound_payment_method_line_id": False,
                "outbound_payment_method_line_id": False,
            }
        )
        self.multi_currency_config.payment_method_ids = [(4, method.id)]
        self.config = self.multi_currency_config
        session = self.open_new_session(0)
        session.try_cash_in_out(
            "in",
            8.0,
            "Suspense float",
            {
                "translatedType": "in",
                "formattedAmount": "8.00",
                "payment_method_id": method.id,
            },
        )
        move = session.statement_line_ids.filtered(
            lambda line: line.amount == 8.0 and line.journal_id == suspense_journal
        )
        self.assertEqual(len(move), 1)
        suspense = suspense_journal.suspense_account_id
        self.assertTrue(suspense)
        self._assert_counterpart_account(move, suspense)
        self.assertFalse(
            move.move_id.line_ids.filtered(
                lambda line: line.account_id == self.outstanding_receipts
            )
        )

    def test_cash_out_uses_chart_outstanding_when_line_account_empty(self):
        inbound = self.eur_cash_journal.inbound_payment_method_line_ids[:1]
        outbound = self.eur_cash_journal.outbound_payment_method_line_ids[:1]
        inbound.payment_account_id = False
        outbound.payment_account_id = False
        self.eur_cash_payment_method.write(
            {
                "inbound_payment_method_line_id": inbound.id,
                "outbound_payment_method_line_id": outbound.id,
            }
        )
        chart = self.env["account.chart.template"]
        expected_inbound = chart.ref(
            "account_journal_payment_debit_account_id", raise_if_not_found=False
        )
        expected_outbound = chart.ref(
            "account_journal_payment_credit_account_id", raise_if_not_found=False
        )
        self.assertTrue(expected_inbound)
        self.assertTrue(expected_outbound)
        self.assertNotEqual(expected_inbound, expected_outbound)

        self.config = self.multi_currency_config
        session = self.open_new_session(0)
        session.try_cash_in_out(
            "in",
            5.0,
            "Chart inbound",
            {
                "translatedType": "in",
                "formattedAmount": "5.00",
                "payment_method_id": self.eur_cash_payment_method.id,
            },
        )
        session.try_cash_in_out(
            "out",
            3.0,
            "Chart outbound",
            {
                "translatedType": "out",
                "formattedAmount": "3.00",
                "payment_method_id": self.eur_cash_payment_method.id,
            },
        )
        cash_in = session.statement_line_ids.filtered(
            lambda line: line.journal_id == self.eur_cash_journal and line.amount > 0
        )[-1:]
        cash_out = session.statement_line_ids.filtered(
            lambda line: line.journal_id == self.eur_cash_journal and line.amount < 0
        )[-1:]
        self._assert_counterpart_account(cash_in, expected_inbound)
        self._assert_counterpart_account(cash_out, expected_outbound)

    def test_bank_payment_outstanding_follows_inbound_outbound_lines(self):
        inbound = self.eur_bank_journal.inbound_payment_method_line_ids[:1]
        outbound = self.eur_bank_journal.outbound_payment_method_line_ids[:1]
        inbound.payment_account_id = self.outstanding_receipts
        outbound.payment_account_id = self.outstanding_payments
        wrong_outstanding = self.company_data["default_account_receivable"]
        self.eur_bank_payment_method.write(
            {
                "outstanding_account_id": wrong_outstanding.id,
                "inbound_payment_method_line_id": inbound.id,
                "outbound_payment_method_line_id": outbound.id,
            }
        )
        self.assertEqual(
            self.eur_bank_payment_method._oca_get_payment_outstanding_account_for_amount(
                50.0
            ),
            self.outstanding_receipts,
        )
        self.assertEqual(
            self.eur_bank_payment_method._oca_get_payment_outstanding_account_for_amount(
                -50.0
            ),
            self.outstanding_payments,
        )

        self.config = self.multi_currency_config
        session = self.open_new_session(0)
        self.assertEqual(
            session._oca_get_force_outstanding_account(
                self.eur_bank_payment_method,
                {"amount": -20.0},
            ),
            self.outstanding_payments,
        )
        self.assertEqual(
            session._oca_get_force_outstanding_account(
                self.eur_bank_payment_method,
                {"amount": 20.0},
            ),
            self.outstanding_receipts,
        )
        self.assertEqual(
            self.eur_bank_payment_method.outstanding_account_id,
            wrong_outstanding,
        )

        order_data = self.create_ui_order_data(
            [(self.product_mc, 1)],
            payments=[(self.eur_bank_payment_method, 100.0)],
        )
        self.env["pos.order"].sync_from_ui([order_data])
        session.action_pos_session_closing_control()
        self.assertEqual(session.state, "closed")
        inbound_pay = self.env["account.payment"].search(
            [
                ("pos_session_id", "=", session.id),
                ("payment_type", "=", "inbound"),
            ]
        )
        self.assertTrue(inbound_pay)
        self.assertEqual(
            inbound_pay.force_outstanding_account_id,
            self.outstanding_receipts,
        )
        self.assertEqual(
            self.eur_bank_payment_method.outstanding_account_id,
            wrong_outstanding,
        )
