# Part of Odoo. See LICENSE file for full copyright and licensing details.

from dateutil.relativedelta import relativedelta

from odoo import Command, fields
from odoo.tests import tagged

from .common import L10nVeSeniatCommon


@tagged("post_install", "-at_install")
class TestAccountPayment(L10nVeSeniatCommon):
    def test_payment_is_retention_field(self):
        partner = self.env["res.partner"].create(
            {
                "name": "Partner",
                "country_id": self.env.ref("base.ve").id,
                "vat": "J12345678",
            }
        )
        move = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": partner.id,
                "invoice_date": fields.Date.today(),
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Line",
                            "quantity": 1.0,
                            "price_unit": 100.0,
                            "account_id": self.company_data[
                                "default_account_revenue"
                            ].id,
                            "tax_ids": [
                                (6, 0, [self.company_data["default_tax_sale"].id])
                            ],
                        },
                    )
                ],
            }
        )
        move.action_post()
        wizard = (
            self.env["account.payment.register"]
            .with_context(active_model="account.move", active_ids=move.ids)
            .create({"payment_date": fields.Date.today()})
        )
        payments = wizard._create_payments()
        payment = payments[0] if len(payments) > 1 else payments
        payment.is_retention = True
        self.assertTrue(payment.is_retention)

    def test_l10n_ve_process_date_on_payment_validation(self):
        partner = self.env["res.partner"].create(
            {
                "name": "Partner proceso",
                "country_id": self.env.ref("base.ve").id,
                "vat": "J87654321",
            }
        )
        move = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": partner.id,
                "invoice_date": fields.Date.today(),
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Line",
                            "quantity": 1.0,
                            "price_unit": 100.0,
                            "account_id": self.company_data[
                                "default_account_revenue"
                            ].id,
                            "tax_ids": [
                                (6, 0, [self.company_data["default_tax_sale"].id])
                            ],
                        },
                    )
                ],
            }
        )
        move.action_post()
        wizard = (
            self.env["account.payment.register"]
            .with_context(active_model="account.move", active_ids=move.ids)
            .create({"payment_date": fields.Date.today()})
        )
        payments = wizard._create_payments()
        payment = payments[0] if len(payments) > 1 else payments
        payment.action_post()
        self.assertIn(payment.state, ("in_process", "paid"))
        self.assertEqual(payment.l10n_ve_process_date, fields.Date.today())
        self.assertEqual(payment.move_id.l10n_ve_process_date, fields.Date.today())

    def test_l10n_ve_process_date_from_payment_before_validation(self):
        partner = self.env["res.partner"].create(
            {
                "name": "Partner fecha pago",
                "country_id": self.env.ref("base.ve").id,
                "vat": "J11223344",
            }
        )
        move = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": partner.id,
                "invoice_date": fields.Date.today(),
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Line",
                            "quantity": 1.0,
                            "price_unit": 100.0,
                            "account_id": self.company_data[
                                "default_account_revenue"
                            ].id,
                            "tax_ids": [
                                (6, 0, [self.company_data["default_tax_sale"].id])
                            ],
                        },
                    )
                ],
            }
        )
        move.action_post()
        custom_date = fields.Date.today() - relativedelta(days=3)
        wizard = (
            self.env["account.payment.register"]
            .with_context(active_model="account.move", active_ids=move.ids)
            .create({"payment_date": fields.Date.today()})
        )
        payments = wizard._create_payments()
        payment = payments[0] if len(payments) > 1 else payments
        payment.l10n_ve_process_date = custom_date
        payment.action_post()
        self.assertEqual(payment.l10n_ve_process_date, custom_date)
        self.assertEqual(payment.move_id.l10n_ve_process_date, custom_date)


@tagged("post_install", "-at_install")
class TestAccountPaymentRegisterSameDay(L10nVeSeniatCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ves = cls.env.ref("base.VES")
        cls.usd = cls.env.ref("base.USD")
        cls.ves.active = True
        cls.usd.active = True
        cls.env.company.currency_id = cls.ves
        cls.company_data["default_journal_bank"].currency_id = False
        cls.company_data["default_journal_sale"].currency_id = False
        cls.partner_ve = cls.env["res.partner"].create(
            {
                "name": "Partner pago mismo dia",
                "country_id": cls.env.ref("base.ve").id,
                "vat": "J55667788",
            }
        )
        cls.invoice_date = fields.Date.today()
        cls.usd_inverse_rate = 438.21789
        rate = cls.env["res.currency.rate"].search(
            [
                ("name", "=", cls.invoice_date),
                ("currency_id", "=", cls.usd.id),
                ("company_id", "=", cls.env.company.id),
            ],
            limit=1,
        )
        if rate:
            rate.inverse_company_rate = cls.usd_inverse_rate
        else:
            cls.env["res.currency.rate"].create(
                {
                    "name": cls.invoice_date,
                    "currency_id": cls.usd.id,
                    "company_id": cls.env.company.id,
                    "inverse_company_rate": cls.usd_inverse_rate,
                }
            )

    def _create_usd_invoice(
        self, amounts, invoice_date=None, move_type="out_invoice", extra_vals=None
    ):
        invoice_date = invoice_date or self.invoice_date
        if move_type in ("in_invoice", "in_refund"):
            tax = self.company_data["default_tax_purchase"]
            account = self.company_data["default_account_expense"]
        else:
            tax = self.company_data["default_tax_sale"]
            account = self.company_data["default_account_revenue"]
        vals = {
            "move_type": move_type,
            "partner_id": self.partner_ve.id,
            "currency_id": self.usd.id,
            "invoice_date": invoice_date,
            "date": invoice_date,
            "invoice_line_ids": [
                Command.create(
                    {
                        "name": "Line %s" % index,
                        "quantity": 1.0,
                        "price_unit": amount,
                        "account_id": account.id,
                        "tax_ids": [Command.set(tax.ids)] if tax else [],
                    }
                )
                for index, amount in enumerate(amounts, start=1)
            ],
        }
        if extra_vals:
            vals.update(extra_vals)
        invoice = self.env["account.move"].create(vals)
        invoice.action_post()
        return invoice

    def _create_payment_register(self, invoice, payment_date, currency):
        return (
            self.env["account.payment.register"]
            .with_context(active_model="account.move", active_ids=invoice.ids)
            .create(
                {
                    "payment_date": payment_date,
                    "journal_id": self.company_data["default_journal_bank"].id,
                    "currency_id": currency.id,
                }
            )
        )

    def _payment_term_residual(self, invoice):
        return abs(
            sum(
                invoice.line_ids.filtered(
                    lambda line: line.display_type == "payment_term"
                ).mapped("amount_residual")
            )
        )

    def _pay_amount(self, invoice, payment_date, currency, amount):
        wizard = self._create_payment_register(invoice, payment_date, currency)
        wizard.amount = amount
        wizard._create_payments()
        invoice.invalidate_recordset()
        return wizard

    def _set_usd_inverse_rate(self, rate_date, inverse_rate):
        Rate = self.env["res.currency.rate"].with_context(
            l10n_ve_skip_currency_rate_validation=True
        )
        rate = Rate.search(
            [
                ("name", "=", rate_date),
                ("currency_id", "=", self.usd.id),
                ("company_id", "=", self.env.company.id),
            ],
            limit=1,
        )
        if rate:
            rate.inverse_company_rate = inverse_rate
        else:
            Rate.create(
                {
                    "name": rate_date,
                    "currency_id": self.usd.id,
                    "company_id": self.env.company.id,
                    "inverse_company_rate": inverse_rate,
                }
            )

    def test_same_day_ves_payment_uses_tax_totals(self):
        invoice = self._create_usd_invoice([10.17, 25.33, 8.91])
        tax_totals_ves = invoice.tax_totals["total_amount"]
        wizard = self._create_payment_register(
            invoice, self.invoice_date, self.ves
        )
        self.assertEqual(
            wizard.currency_id.compare_amounts(wizard.amount, tax_totals_ves),
            0,
        )

    def test_later_day_ves_payment_uses_current_rate(self):
        invoice = self._create_usd_invoice([10.17, 25.33, 8.91])
        later = self.invoice_date + relativedelta(days=2)
        self._set_usd_inverse_rate(later, 450.5)
        wizard = self._create_payment_register(invoice, later, self.ves)
        expected = self.usd._convert(
            invoice.amount_residual,
            self.ves,
            self.env.company,
            later,
        )
        self.assertEqual(
            wizard.currency_id.compare_amounts(wizard.amount, expected),
            0,
        )
        self.assertNotEqual(
            wizard.currency_id.compare_amounts(
                wizard.amount, invoice.tax_totals["total_amount"]
            ),
            0,
        )

    def test_mixed_same_day_ves_payment_uses_current_rate(self):
        invoice = self._create_usd_invoice([100.0])
        usd_wizard = self._create_payment_register(
            invoice, self.invoice_date, self.usd
        )
        usd_wizard.amount = 40.0
        usd_wizard._create_payments()
        invoice.invalidate_recordset()
        wizard = self._create_payment_register(
            invoice, self.invoice_date, self.ves
        )
        expected = abs(sum(invoice.line_ids.filtered(
            lambda line: line.display_type == "payment_term"
        ).mapped("amount_residual")))
        self.assertEqual(
            wizard.currency_id.compare_amounts(wizard.amount, expected),
            0,
        )
        self.assertNotEqual(
            wizard.currency_id.compare_amounts(
                wizard.amount, invoice.tax_totals["total_amount"]
            ),
            0,
        )

    def test_same_day_ves_partial_keeps_fiscal_residual(self):
        invoice = self._create_usd_invoice([10.17, 25.33, 8.91])
        fiscal_ves = invoice.tax_totals["total_amount"]
        first = self._create_payment_register(
            invoice, self.invoice_date, self.ves
        )
        first.amount = 1000.0
        first._create_payments()
        invoice.invalidate_recordset()
        leftover = abs(sum(invoice.line_ids.filtered(
            lambda line: line.display_type == "payment_term"
        ).mapped("amount_residual")))
        self.assertEqual(
            self.ves.compare_amounts(leftover, fiscal_ves - 1000.0),
            0,
        )
        wizard = self._create_payment_register(
            invoice, self.invoice_date, self.ves
        )
        self.assertEqual(
            wizard.currency_id.compare_amounts(wizard.amount, leftover),
            0,
        )

    def test_same_day_two_ves_partials_then_remainder(self):
        invoice = self._create_usd_invoice([10.17, 25.33, 8.91])
        fiscal_ves = invoice.tax_totals["total_amount"]
        self._pay_amount(invoice, self.invoice_date, self.ves, 1000.0)
        self._pay_amount(invoice, self.invoice_date, self.ves, 1500.0)
        leftover = self._payment_term_residual(invoice)
        self.assertEqual(
            self.ves.compare_amounts(leftover, fiscal_ves - 2500.0),
            0,
        )
        wizard = self._create_payment_register(
            invoice, self.invoice_date, self.ves
        )
        self.assertEqual(
            wizard.currency_id.compare_amounts(wizard.amount, leftover),
            0,
        )

    def test_same_day_pay_one_hundred_less_than_fiscal(self):
        invoice = self._create_usd_invoice([10.17, 25.33, 8.91])
        fiscal_ves = invoice.tax_totals["total_amount"]
        self._pay_amount(invoice, self.invoice_date, self.ves, fiscal_ves - 100.0)
        leftover = self._payment_term_residual(invoice)
        self.assertEqual(self.ves.compare_amounts(leftover, 100.0), 0)
        wizard = self._create_payment_register(
            invoice, self.invoice_date, self.ves
        )
        self.assertEqual(
            wizard.currency_id.compare_amounts(wizard.amount, 100.0),
            0,
        )

    def test_same_day_pay_non_fiscal_amount_keeps_ves_gap(self):
        invoice = self._create_usd_invoice([10.17, 25.33, 8.91])
        fiscal_ves = invoice.tax_totals["total_amount"]
        converted = self.usd._convert(
            invoice.amount_total,
            self.ves,
            self.env.company,
            self.invoice_date,
        )
        paid = converted
        if self.ves.compare_amounts(converted, fiscal_ves) == 0:
            paid = self.ves.round(fiscal_ves - 5.58)
        self._pay_amount(invoice, self.invoice_date, self.ves, paid)
        leftover = self._payment_term_residual(invoice)
        self.assertEqual(
            self.ves.compare_amounts(leftover, fiscal_ves - paid),
            0,
        )
        wizard = self._create_payment_register(
            invoice, self.invoice_date, self.ves
        )
        self.assertEqual(
            wizard.currency_id.compare_amounts(wizard.amount, leftover),
            0,
        )

    def test_later_day_after_ves_partial_uses_new_rate(self):
        invoice = self._create_usd_invoice([10.17, 25.33, 8.91])
        fiscal_ves = invoice.tax_totals["total_amount"]
        self._pay_amount(invoice, self.invoice_date, self.ves, 1000.0)
        later = self.invoice_date + relativedelta(days=2)
        self._set_usd_inverse_rate(later, 450.5)
        leftover_usd = abs(
            sum(
                invoice.line_ids.filtered(
                    lambda line: line.display_type == "payment_term"
                ).mapped("amount_residual_currency")
            )
        )
        wizard = self._create_payment_register(invoice, later, self.ves)
        expected = self.usd._convert(
            leftover_usd,
            self.ves,
            self.env.company,
            later,
        )
        self.assertEqual(
            wizard.currency_id.compare_amounts(wizard.amount, expected),
            0,
        )
        self.assertNotEqual(
            wizard.currency_id.compare_amounts(wizard.amount, fiscal_ves - 1000.0),
            0,
        )

    def test_same_day_usd_then_ves_then_ves_remainder(self):
        invoice = self._create_usd_invoice([100.0])
        self._pay_amount(invoice, self.invoice_date, self.usd, 40.0)
        after_usd = self._payment_term_residual(invoice)
        self._pay_amount(invoice, self.invoice_date, self.ves, 1000.0)
        leftover = self._payment_term_residual(invoice)
        self.assertEqual(
            self.ves.compare_amounts(leftover, after_usd - 1000.0),
            0,
        )
        wizard = self._create_payment_register(
            invoice, self.invoice_date, self.ves
        )
        self.assertEqual(
            wizard.currency_id.compare_amounts(wizard.amount, leftover),
            0,
        )

    def test_same_day_two_invoices_sum_tax_totals(self):
        invoice_a = self._create_usd_invoice([10.17, 8.91])
        invoice_b = self._create_usd_invoice([25.33])
        expected = self.ves.round(
            invoice_a.tax_totals["total_amount"]
            + invoice_b.tax_totals["total_amount"]
        )
        wizard = (
            self.env["account.payment.register"]
            .with_context(
                active_model="account.move",
                active_ids=(invoice_a + invoice_b).ids,
            )
            .create(
                {
                    "payment_date": self.invoice_date,
                    "journal_id": self.company_data["default_journal_bank"].id,
                    "currency_id": self.ves.id,
                }
            )
        )
        self.assertEqual(
            wizard.currency_id.compare_amounts(wizard.amount, expected),
            0,
        )

    def test_same_day_vendor_bill_uses_tax_totals(self):
        bill = self._create_usd_invoice([12.5, 7.3], move_type="in_invoice")
        wizard = self._create_payment_register(
            bill, self.invoice_date, self.ves
        )
        self.assertEqual(
            wizard.currency_id.compare_amounts(
                wizard.amount, bill.tax_totals["total_amount"]
            ),
            0,
        )

    def test_same_day_vendor_bill_partial_keeps_fiscal_residual(self):
        bill = self._create_usd_invoice([12.5, 7.3], move_type="in_invoice")
        fiscal_ves = bill.tax_totals["total_amount"]
        self._pay_amount(bill, self.invoice_date, self.ves, 500.0)
        leftover = self._payment_term_residual(bill)
        self.assertEqual(
            self.ves.compare_amounts(leftover, fiscal_ves - 500.0),
            0,
        )
        wizard = self._create_payment_register(bill, self.invoice_date, self.ves)
        self.assertEqual(
            wizard.currency_id.compare_amounts(wizard.amount, leftover),
            0,
        )

    def test_same_day_tiny_invoice_uses_tax_totals(self):
        invoice = self._create_usd_invoice([0.1])
        wizard = self._create_payment_register(
            invoice, self.invoice_date, self.ves
        )
        self.assertEqual(
            wizard.currency_id.compare_amounts(
                wizard.amount, invoice.tax_totals["total_amount"]
            ),
            0,
        )

    def test_same_day_pay_exact_leftover_closes_invoice(self):
        invoice = self._create_usd_invoice([10.17, 25.33, 8.91])
        self._pay_amount(invoice, self.invoice_date, self.ves, 1000.0)
        leftover = self._payment_term_residual(invoice)
        self._pay_amount(invoice, self.invoice_date, self.ves, leftover)
        self.assertTrue(self.usd.is_zero(invoice.amount_residual))
        self.assertTrue(self.ves.is_zero(self._payment_term_residual(invoice)))

    def test_same_day_three_small_ves_payments(self):
        invoice = self._create_usd_invoice([6.9])
        fiscal_ves = invoice.tax_totals["total_amount"]
        self._pay_amount(invoice, self.invoice_date, self.ves, 1.0)
        self._pay_amount(invoice, self.invoice_date, self.ves, 2.0)
        self._pay_amount(invoice, self.invoice_date, self.ves, 3.0)
        leftover = self._payment_term_residual(invoice)
        self.assertEqual(
            self.ves.compare_amounts(leftover, fiscal_ves - 6.0),
            0,
        )

    def test_same_day_payment_terms_both_due_use_tax_totals(self):
        term = self.env["account.payment.term"].create({"name": "50-50 same day"})
        first_line = term.line_ids[:1]
        first_line.write({"value_amount": 50.0, "nb_days": 0})
        extra_line = self.env["account.payment.term.line"].create(
            {
                "payment_id": term.id,
                "value": "percent",
                "value_amount": 50.0,
                "nb_days": 0,
            }
        )
        extra_line.write({"value_amount": 50.0, "nb_days": 0})
        term.line_ids.write({"nb_days": 0})
        invoice = self._create_usd_invoice(
            [100.0], extra_vals={"invoice_payment_term_id": term.id}
        )
        wizard = self._create_payment_register(
            invoice, self.invoice_date, self.ves
        )
        self.assertEqual(
            wizard.currency_id.compare_amounts(
                wizard.amount, invoice.tax_totals["total_amount"]
            ),
            0,
        )
