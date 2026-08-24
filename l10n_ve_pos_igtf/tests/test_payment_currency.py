from odoo import Command
from odoo.tests import tagged

from odoo.addons.l10n_ve_igtf.tests.common import TestL10nVeIgtfCommon
from odoo.addons.point_of_sale.tests.common import TestPointOfSaleCommon


@tagged("post_install", "-at_install")
class TestPosIgtfPaymentCurrency(TestL10nVeIgtfCommon):
    def _create_bank_payment_method(self, currency, code):
        journal = self.env["account.journal"].create(
            {
                "name": f"{currency.name} POS Bank IGTF",
                "type": "bank",
                "code": code,
                "currency_id": currency.id,
            }
        )
        return self.env["pos.payment.method"].create(
            {
                "name": f"{currency.name} Bank IGTF",
                "journal_id": journal.id,
                "receivable_account_id": self.receivable_account.id,
                "company_id": self.company.id,
            }
        )

    def test_payment_method_currency_follows_journal(self):
        usd_method = self._create_bank_payment_method(self.usd, "IUSD")
        ves_method = self._create_bank_payment_method(self.ves, "IVES")
        self.assertEqual(usd_method.payment_currency_id, self.usd)
        self.assertEqual(ves_method.payment_currency_id, self.ves)

    def test_payment_method_without_journal_currency_uses_company(self):
        journal = self.env["account.journal"].create(
            {
                "name": "Company Currency POS Bank",
                "type": "bank",
                "code": "ICMP",
            }
        )
        method = self.env["pos.payment.method"].create(
            {
                "name": "Company Bank IGTF",
                "journal_id": journal.id,
                "receivable_account_id": self.receivable_account.id,
                "company_id": self.company.id,
            }
        )
        self.assertEqual(method.payment_currency_id, self.company.currency_id)

    def test_load_pos_data_includes_payment_currency(self):
        method_fields = self.env["pos.payment.method"]._load_pos_data_fields(False)
        self.assertIn("payment_currency_id", method_fields)


@tagged("post_install", "-at_install")
class TestPosIgtfAppliesByCurrency(TestPointOfSaleCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.usd = cls.env.ref("base.USD")
        cls.ves = cls.env.ref("base.VES")
        cls.ves.active = True
        cls.usd.active = True
        igtf_account = cls.env["account.account"].create(
            {
                "name": "IGTF POS Test",
                "code": "2102199",
                "account_type": "liability_current",
                "company_ids": [Command.set([cls.company.id])],
                "reconcile": True,
            }
        )
        cls.company.partner_id.write(
            {
                "country_id": cls.env.ref("base.ve").id,
                "taxpayer_type": "special",
            }
        )
        cls.company.write(
            {
                "account_fiscal_country_id": cls.env.ref("base.ve").id,
                "l10n_ve_igtf_account_id": igtf_account.id,
                "l10n_ve_igtf_percent": 3.0,
                "l10n_ve_igtf_currency_ids": [Command.set([cls.usd.id])],
            }
        )
        cls.usd_journal = cls.env["account.journal"].create(
            {
                "name": "USD POS IGTF",
                "type": "bank",
                "code": "PUSD",
                "currency_id": cls.usd.id,
            }
        )
        cls.usd_method = cls.env["pos.payment.method"].create(
            {
                "name": "USD IGTF",
                "journal_id": cls.usd_journal.id,
                "receivable_account_id": cls.company_data[
                    "default_account_receivable"
                ].id,
                "company_id": cls.company.id,
            }
        )
        cls.ves_journal = cls.env["account.journal"].create(
            {
                "name": "VES POS IGTF",
                "type": "bank",
                "code": "PVES",
                "currency_id": cls.ves.id,
            }
        )
        cls.ves_method = cls.env["pos.payment.method"].create(
            {
                "name": "VES IGTF",
                "journal_id": cls.ves_journal.id,
                "receivable_account_id": cls.company_data[
                    "default_account_receivable"
                ].id,
                "company_id": cls.company.id,
            }
        )
        cls.pos_config.write(
            {
                "payment_method_ids": [
                    Command.link(cls.cash_payment_method.id),
                    Command.link(cls.usd_method.id),
                    Command.link(cls.ves_method.id),
                ]
            }
        )

    def _create_draft_order(self):
        self.pos_config.open_ui()
        session = self.pos_config.current_session_id
        return self.env["pos.order"].create(
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

    def test_usd_payment_applies_igtf_by_currency(self):
        order = self._create_draft_order()
        usd_payment = self.env["pos.payment"].create(
            {
                "pos_order_id": order.id,
                "amount": 50.0,
                "payment_method_id": self.usd_method.id,
            }
        )
        ves_payment = self.env["pos.payment"].create(
            {
                "pos_order_id": order.id,
                "amount": 50.0,
                "payment_method_id": self.ves_method.id,
            }
        )
        self.assertEqual(usd_payment.payment_currency_id, self.usd)
        self.assertEqual(ves_payment.payment_currency_id, self.ves)
        self.assertTrue(usd_payment._l10n_ve_pos_payment_applies_igtf_by_currency())
        self.assertFalse(ves_payment._l10n_ve_pos_payment_applies_igtf_by_currency())
