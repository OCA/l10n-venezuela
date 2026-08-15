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
        self.assertEqual(payment.state, "in_process")
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

    def _create_usd_invoice(self, amounts, invoice_date=None):
        invoice_date = invoice_date or self.invoice_date
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
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
                            "account_id": self.company_data[
                                "default_account_revenue"
                            ].id,
                            "tax_ids": [
                                Command.set(
                                    [self.company_data["default_tax_sale"].id]
                                )
                            ],
                        }
                    )
                    for index, amount in enumerate(amounts, start=1)
                ],
            }
        )
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
        self.env["res.currency.rate"].create(
            {
                "name": later,
                "currency_id": self.usd.id,
                "company_id": self.env.company.id,
                "inverse_company_rate": 450.5,
            }
        )
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
        expected = self.usd._convert(
            invoice.amount_residual,
            self.ves,
            self.env.company,
            self.invoice_date,
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
