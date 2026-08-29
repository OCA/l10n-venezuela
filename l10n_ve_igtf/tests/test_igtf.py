# Copyright 2026 BWEALTHICS LLC
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged("post_install", "-at_install")
class TestIgtf(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.company_data["company"]
        cls.expense_account = cls.env["account.account"].create(
            {
                "code": "IGTFEXP",
                "name": "IGTF Expense",
                "account_type": "expense",
            }
        )
        cls.perception_account = cls.env["account.account"].create(
            {
                "code": "IGTFPAY",
                "name": "IGTF Perception Payable",
                "account_type": "liability_current",
            }
        )
        cls.company.write(
            {
                "l10n_ve_igtf_rate": 3.0,
                "l10n_ve_igtf_expense_account_id": cls.expense_account.id,
                "l10n_ve_igtf_perception_account_id": cls.perception_account.id,
            }
        )
        cls.journal = cls.company_data["default_journal_bank"]
        cls.journal.l10n_ve_igtf_enabled = True

    def _create_payment(self, payment_type, apply_igtf=True, date="2026-07-10"):
        return self.env["account.payment"].create(
            {
                "payment_type": payment_type,
                "partner_type": (
                    "supplier" if payment_type == "outbound" else "customer"
                ),
                "partner_id": self.partner_a.id,
                "amount": 100.0,
                "date": date,
                "journal_id": self.journal.id,
                "l10n_ve_igtf_apply": apply_igtf,
                "l10n_ve_igtf_rate": 3.0,
            }
        )

    def _assert_move_balanced(self, payment):
        self.assertEqual(len(payment.move_id), 1)
        self.assertTrue(
            payment.company_currency_id.is_zero(
                sum(payment.move_id.line_ids.mapped("balance"))
            )
        )

    def _create_bill(self, amount=100.0):
        bill = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": self.partner_a.id,
                "invoice_date": "2026-07-10",
                "date": "2026-07-10",
                "invoice_line_ids": [
                    Command.create(
                        {
                            "name": "Test service",
                            "quantity": 1.0,
                            "price_unit": amount,
                            "tax_ids": [],
                        }
                    )
                ],
            }
        )
        bill.action_post()
        return bill

    def test_outbound_igtf_is_part_of_payment_move(self):
        payment = self._create_payment("outbound")
        payment.action_post()

        self._assert_move_balanced(payment)
        liquidity, counterpart, other = payment._seek_for_lines()
        self.assertEqual(len(other), 1)
        self.assertEqual(other.account_id, self.expense_account)
        self.assertTrue(other.l10n_ve_igtf_line)
        self.assertAlmostEqual(other.amount_currency, 3.0)
        self.assertAlmostEqual(sum(liquidity.mapped("amount_currency")), -103.0)
        self.assertAlmostEqual(sum(counterpart.mapped("amount_currency")), 100.0)

    def test_outbound_without_explicit_selection_has_no_igtf(self):
        payment = self._create_payment("outbound", apply_igtf=False)
        payment.action_post()

        self._assert_move_balanced(payment)
        _liquidity, _counterpart, other = payment._seek_for_lines()
        self.assertFalse(other)

    def test_draft_payment_resynchronizes_igtf_lines(self):
        payment = self._create_payment("outbound")
        payment.action_post()
        payment.action_draft()

        payment.l10n_ve_igtf_apply = False

        _liquidity, _counterpart, other = payment._seek_for_lines()
        self.assertFalse(other)

    def test_draft_payment_resynchronizes_igtf_amount(self):
        payment = self._create_payment("outbound")
        payment.action_post()
        payment.action_draft()

        payment.amount = 200.0

        liquidity, _counterpart, other = payment._seek_for_lines()
        self.assertEqual(len(other), 1)
        self.assertAlmostEqual(other.amount_currency, 6.0)
        self.assertAlmostEqual(sum(liquidity.mapped("amount_currency")), -206.0)

    def test_draft_payment_resynchronizes_igtf_rate(self):
        payment = self._create_payment("outbound")
        payment.action_post()
        payment.action_draft()

        payment.l10n_ve_igtf_rate = 5.0

        liquidity, _counterpart, other = payment._seek_for_lines()
        self.assertEqual(len(other), 1)
        self.assertAlmostEqual(other.amount_currency, 5.0)
        self.assertAlmostEqual(sum(liquidity.mapped("amount_currency")), -105.0)

    def test_inbound_perception_is_part_of_payment_move(self):
        self.company.write(
            {
                "l10n_ve_igtf_perception_agent": True,
                "l10n_ve_igtf_perception_agent_date": "2026-01-01",
            }
        )
        payment = self._create_payment("inbound")
        payment.action_post()

        self._assert_move_balanced(payment)
        liquidity, counterpart, other = payment._seek_for_lines()
        self.assertEqual(len(other), 1)
        self.assertEqual(other.account_id, self.perception_account)
        self.assertAlmostEqual(other.amount_currency, -3.0)
        self.assertAlmostEqual(sum(liquidity.mapped("amount_currency")), 103.0)
        self.assertAlmostEqual(sum(counterpart.mapped("amount_currency")), -100.0)

    def test_inbound_requires_perception_agent(self):
        payment = self._create_payment("inbound")
        with self.assertRaises(UserError), self.env.cr.savepoint():
            payment.action_post()

    def test_inbound_before_designation_date_is_rejected(self):
        self.company.write(
            {
                "l10n_ve_igtf_perception_agent": True,
                "l10n_ve_igtf_perception_agent_date": "2026-08-01",
            }
        )
        payment = self._create_payment("inbound")
        with self.assertRaises(UserError), self.env.cr.savepoint():
            payment.action_post()

    def test_outbound_requires_expense_account(self):
        self.company.l10n_ve_igtf_expense_account_id = False
        payment = self._create_payment("outbound")
        with self.assertRaises(UserError), self.env.cr.savepoint():
            payment.action_post()

    def test_register_payment_passes_explicit_igtf_selection(self):
        bill = self._create_bill()
        wizard = (
            self.env["account.payment.register"]
            .with_context(active_model="account.move", active_ids=bill.ids)
            .create(
                {
                    "journal_id": self.journal.id,
                    "payment_date": "2026-07-10",
                    "l10n_ve_igtf_apply": True,
                }
            )
        )

        payment = wizard._create_payments()

        self.assertTrue(payment.l10n_ve_igtf_apply)
        self.assertAlmostEqual(payment.l10n_ve_igtf_rate, 3.0)
        self.assertEqual(
            payment.move_id.line_ids.filtered(
                lambda line: line.account_id == self.expense_account
            ).amount_currency,
            3.0,
        )

    def test_register_payment_split_batch_keeps_igtf_selection(self):
        bills = self._create_bill(100.0) | self._create_bill(200.0)
        wizard = (
            self.env["account.payment.register"]
            .with_context(active_model="account.move", active_ids=bills.ids)
            .create(
                {
                    "journal_id": self.journal.id,
                    "payment_date": "2026-07-10",
                    "group_payment": False,
                    "l10n_ve_igtf_apply": True,
                }
            )
        )

        payments = wizard._create_payments()

        self.assertEqual(len(payments), 2)
        self.assertTrue(all(payments.mapped("l10n_ve_igtf_apply")))
        self.assertEqual(
            sorted(payments.mapped("l10n_ve_igtf_amount")),
            [3.0, 6.0],
        )

    def test_register_payment_rejects_writeoff_with_igtf(self):
        wizard = self.env["account.payment.register"].new(
            {
                "company_id": self.company.id,
                "journal_id": self.journal.id,
                "l10n_ve_igtf_apply": True,
            }
        )

        with self.assertRaises(UserError):
            wizard._l10n_ve_add_igtf_payment_vals(
                {"write_off_line_vals": [{"account_id": self.expense_account.id}]}
            )

    def test_payment_rejects_writeoff_with_igtf(self):
        payment = self._create_payment("outbound")

        with self.assertRaises(UserError):
            payment._prepare_move_lines_per_type(
                write_off_line_vals=[
                    {
                        "name": "Payment difference",
                        "account_id": self.expense_account.id,
                        "partner_id": self.partner_a.id,
                        "currency_id": payment.currency_id.id,
                        "amount_currency": 1.0,
                        "balance": 1.0,
                    }
                ]
            )
