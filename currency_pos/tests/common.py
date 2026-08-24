from odoo import fields
from odoo.addons.point_of_sale.tests.common import TestPoSCommon


class TestPosPaymentCurrencyCommon(TestPoSCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if not hasattr(cls, "cash_payment_method"):
            cls.company_data["default_journal_cash"].pos_payment_method_ids.unlink()
            cls.cash_payment_method = cls.env["pos.payment.method"].create(
                {
                    "name": "Cash MC",
                    "receivable_account_id": cls.company_data["default_account_receivable"].id,
                    "journal_id": cls.company_data["default_journal_cash"].id,
                    "company_id": cls.env.company.id,
                }
            )
        if not hasattr(cls, "partner1"):
            cls.partner1 = cls.env["res.partner"].create({"name": "Partner MC"})
        cls.usd_currency = cls.company_currency
        cls.eur_currency = cls.setup_other_currency("EUR", rounding=0.01)
        (cls.eur_currency.rate_ids | cls.usd_currency.rate_ids).unlink()
        cls.env["res.currency.rate"].create(
            {
                "name": fields.Date.today(),
                "rate": 2.0,
                "currency_id": cls.eur_currency.id,
            }
        )

        cls.eur_bank_journal = cls.env["account.journal"].create(
            {
                "name": "EUR Bank POS",
                "type": "bank",
                "code": "EURB",
                "currency_id": cls.eur_currency.id,
            }
        )
        cls.eur_bank_payment_method = cls.env["pos.payment.method"].create(
            {
                "name": "Bank EUR",
                "journal_id": cls.eur_bank_journal.id,
                "receivable_account_id": cls.company_data["default_account_receivable"].id,
            }
        )

        cash_journal = cls.company_data["default_journal_cash"]
        profit_account = (
            cash_journal.profit_account_id
            or cls.company.default_cash_difference_income_account_id
        )
        loss_account = (
            cash_journal.loss_account_id
            or cls.company.default_cash_difference_expense_account_id
        )
        if profit_account and not cash_journal.profit_account_id:
            cash_journal.profit_account_id = profit_account
        if loss_account and not cash_journal.loss_account_id:
            cash_journal.loss_account_id = loss_account

        cls.eur_cash_journal = cls.env["account.journal"].create(
            {
                "name": "EUR Cash POS",
                "type": "cash",
                "code": "EURC",
                "currency_id": cls.eur_currency.id,
                "profit_account_id": profit_account.id if profit_account else False,
                "loss_account_id": loss_account.id if loss_account else False,
            }
        )
        cls.eur_cash_payment_method = cls.env["pos.payment.method"].create(
            {
                "name": "Cash EUR",
                "journal_id": cls.eur_cash_journal.id,
                "receivable_account_id": cls.company_data["default_account_receivable"].id,
            }
        )

        cls.multi_currency_config = cls.env["pos.config"].create(
            {
                "name": "POS Multi Currency",
                "journal_id": cls.company_data["default_journal_sale"].id,
                "invoice_journal_id": cls.company_data["default_journal_sale"].id,
                "allow_multi_currency_payment": True,
                "payment_method_ids": [
                    (4, cls.cash_payment_method.id),
                    (4, cls.eur_cash_payment_method.id),
                    (4, cls.eur_bank_payment_method.id),
                ],
            }
        )

        cls.product_mc = cls.create_product(
            "MC Product",
            cls.categ_basic,
            100.0,
            tax_ids=[],
        )
        cls.product_mc.available_in_pos = True
