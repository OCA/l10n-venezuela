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
        cls.bolivar = cls.setup_other_currency("VES")

    def _create_payment(
        self,
        payment_type,
        apply_igtf=True,
        date="2026-07-10",
        rate=3.0,
        currency=None,
        settles_invoice=True,
    ):
        # IGTF is only allowed on payments that settle invoices, so by default
        # the payment is linked to an invoice or bill, as the Register Payment
        # wizard does.
        vals = {
            "payment_type": payment_type,
            "partner_type": ("supplier" if payment_type == "outbound" else "customer"),
            "partner_id": self.partner_a.id,
            "amount": 100.0,
            "date": date,
            "journal_id": self.journal.id,
            "l10n_ve_igtf_apply": apply_igtf,
            "l10n_ve_igtf_rate": rate,
        }
        if currency:
            vals["currency_id"] = currency.id
        if settles_invoice:
            invoice = self._create_bill(
                move_type="in_invoice" if payment_type == "outbound" else "out_invoice"
            )
            vals["invoice_ids"] = [Command.set(invoice.ids)]
        return self.env["account.payment"].create(vals)

    def _assert_move_balanced(self, payment):
        self.assertEqual(len(payment.move_id), 1)
        self.assertTrue(
            payment.company_currency_id.is_zero(
                sum(payment.move_id.line_ids.mapped("balance"))
            )
        )

    def _create_bill(self, amount=100.0, move_type="in_invoice"):
        bill = self.env["account.move"].create(
            {
                "move_type": move_type,
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

    def test_draft_corrections_keep_igtf_exemption(self):
        # An exempt foreign-currency payment (Law article 4(5)/4(6)) must stay
        # without IGTF when its amount, date or journal is corrected while
        # draft: the opt-in is a stored selection, not a computed value.
        other_journal = self.company_data["default_journal_cash"]
        other_journal.l10n_ve_igtf_enabled = True
        payment = self._create_payment("outbound", apply_igtf=False)

        payment.write(
            {
                "amount": 250.0,
                "date": "2026-07-15",
                "journal_id": other_journal.id,
            }
        )
        payment.action_post()

        self.assertFalse(payment.l10n_ve_igtf_apply)
        self.assertFalse(payment.l10n_ve_igtf_amount)
        self.assertFalse(payment.move_id.line_ids.filtered("l10n_ve_igtf_line"))

    def test_draft_corrections_keep_edited_rate(self):
        # A rate adjusted on the payment survives later corrections of the
        # payment amount and date; only the IGTF amount follows them.
        payment = self._create_payment("outbound", rate=5.0)

        payment.write({"amount": 200.0, "date": "2026-07-15"})
        payment.action_post()

        self.assertAlmostEqual(payment.l10n_ve_igtf_rate, 5.0)
        self.assertAlmostEqual(payment.l10n_ve_igtf_amount, 10.0)
        _liquidity, _counterpart, other = payment._seek_for_lines()
        self.assertAlmostEqual(other.amount_currency, 10.0)

    def test_mixed_settlement_taxes_only_selected_portion(self):
        # IGTF is caused by the payment received in foreign currency, not by
        # the invoice taxable base: an invoice settled partly with IGTF and
        # partly without it only carries IGTF on the selected portion, and the
        # IGTF line is not a tax line, so it never reaches a tax report.
        self.company.write(
            {
                "l10n_ve_igtf_perception_agent": True,
                "l10n_ve_igtf_perception_agent_date": "2026-01-01",
            }
        )
        invoice = self._create_bill(100.0, move_type="out_invoice")
        payments = self.env["account.payment"]
        for amount, apply_igtf in ((60.0, True), (40.0, False)):
            wizard = (
                self.env["account.payment.register"]
                .with_context(active_model="account.move", active_ids=invoice.ids)
                .create(
                    {
                        "journal_id": self.journal.id,
                        "payment_date": "2026-07-10",
                        "amount": amount,
                        "l10n_ve_igtf_apply": apply_igtf,
                    }
                )
            )
            payments |= wizard._create_payments()

        self.assertTrue(invoice.currency_id.is_zero(invoice.amount_residual))
        self.assertAlmostEqual(payments[0].l10n_ve_igtf_amount, 1.8)
        self.assertFalse(payments[1].l10n_ve_igtf_amount)
        igtf_lines = payments.move_id.line_ids.filtered("l10n_ve_igtf_line")
        self.assertEqual(len(igtf_lines), 1)
        self.assertAlmostEqual(igtf_lines.amount_currency, -1.8)
        self.assertFalse(igtf_lines.tax_line_id)
        self.assertFalse(igtf_lines.tax_ids)

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

        self.assertEqual(payment.invoice_ids, bill)
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
                {"write_off_line_vals": [{"account_id": self.expense_account.id}]},
                {"lines": self._create_bill().line_ids},
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

    def test_foreign_currency_payment_accepts_igtf(self):
        # Applicability follows the payment currency, not the company one.
        payment = self._create_payment(
            "outbound", currency=self.setup_other_currency("EUR")
        )
        payment.action_post()

        _liquidity, _counterpart, other = payment._seek_for_lines()
        self.assertEqual(other.currency_id.name, "EUR")
        self.assertAlmostEqual(other.amount_currency, 3.0)

    def test_bolivar_payment_rejects_igtf(self):
        with (
            self.assertRaisesRegex(UserError, "bolivars"),
            self.env.cr.savepoint(),
        ):
            self._create_payment("outbound", currency=self.bolivar)

    def test_bolivar_payment_does_not_offer_igtf(self):
        payment = self._create_payment(
            "outbound", apply_igtf=False, currency=self.bolivar
        )
        self.assertFalse(payment.l10n_ve_igtf_available)

        wizard = (
            self.env["account.payment.register"]
            .with_context(
                active_model="account.move", active_ids=self._create_bill().ids
            )
            .create({"journal_id": self.journal.id, "currency_id": self.bolivar.id})
        )
        self.assertFalse(wizard.l10n_ve_igtf_available)
        wizard.currency_id = self.company.currency_id
        self.assertTrue(wizard.l10n_ve_igtf_available)

    def test_advance_payment_rejects_igtf(self):
        with (
            self.assertRaisesRegex(UserError, "settle invoices"),
            self.env.cr.savepoint(),
        ):
            self._create_payment("outbound", settles_invoice=False)

    def test_advance_payment_does_not_offer_igtf(self):
        payment = self._create_payment(
            "outbound", apply_igtf=False, settles_invoice=False
        )
        self.assertFalse(payment.l10n_ve_igtf_available)
        payment.action_post()
        self.assertFalse(payment.move_id.line_ids.filtered("l10n_ve_igtf_line"))

    def test_igtf_cannot_be_written_on_advance_or_bolivar_payment(self):
        advance = self._create_payment(
            "outbound", apply_igtf=False, settles_invoice=False
        )
        advance.action_post()
        with (
            self.assertRaisesRegex(UserError, "settle invoices"),
            self.env.cr.savepoint(),
        ):
            advance.write({"l10n_ve_igtf_apply": True})

        bolivar_payment = self._create_payment("outbound", apply_igtf=False)
        bolivar_payment.currency_id = self.bolivar
        with (
            self.assertRaisesRegex(UserError, "bolivars"),
            self.env.cr.savepoint(),
        ):
            bolivar_payment.write({"l10n_ve_igtf_apply": True})
