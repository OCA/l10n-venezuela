# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import L10nVeSeniatCommon


@tagged("post_install", "-at_install")
class TestResCurrencyRate(L10nVeSeniatCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.usd = cls.env.ref("base.USD")
        cls.today = fields.Date.today()

    def _create_usd_rate(self, inverse_company_rate=40.0):
        return self.env["res.currency.rate"].create(
            {
                "currency_id": self.usd.id,
                "company_id": self.env.company.id,
                "name": self.today,
                "inverse_company_rate": inverse_company_rate,
            }
        )

    def _create_usd_invoice(self, post=False):
        return self._l10n_ve_create_invoice(
            move_type="in_invoice",
            partner=self.partner_a,
            invoice_date=self.today,
            amounts=[100.0],
            taxes=self.company_data["default_tax_purchase"],
            currency=self.usd,
            post=post,
        )

    def test_rate_write_blocked_by_posted_invoice(self):
        rate = self._create_usd_rate()
        invoice = self._create_usd_invoice(post=True)
        self.assertEqual(invoice.state, "posted")

        with self.assertRaises(UserError) as error:
            rate.write({"inverse_company_rate": 45.0})

        self.assertIn("facturas confirmadas", str(error.exception).lower())
        self.assertIn(invoice.name, str(error.exception))

    def test_rate_write_allowed_when_invoice_is_draft(self):
        rate = self._create_usd_rate()
        self._create_usd_invoice(post=False)

        rate.write({"inverse_company_rate": 45.0})
        self.assertEqual(rate.inverse_company_rate, 45.0)

    def test_rate_write_allowed_after_invoice_reset_to_draft(self):
        rate = self._create_usd_rate()
        invoice = self._create_usd_invoice(post=True)
        invoice.button_draft()

        rate.write({"inverse_company_rate": 45.0})
        self.assertEqual(rate.inverse_company_rate, 45.0)

    def test_rate_unlink_blocked_for_ve_company(self):
        rate = self._create_usd_rate()
        with self.assertRaises(UserError) as error:
            rate.unlink()
        self.assertIn("no se pueden eliminar tasas de cambio", str(error.exception).lower())

    def test_draft_invoice_currency_rate_outdated_alert(self):
        rate = self._create_usd_rate(inverse_company_rate=40.0)
        invoice = self._create_usd_invoice(post=False)
        self.assertFalse(invoice.l10n_ve_currency_rate_outdated)

        rate.write({"inverse_company_rate": 50.0})
        invoice.invalidate_recordset(
            ["expected_currency_rate", "l10n_ve_currency_rate_outdated"]
        )
        self.assertTrue(invoice.l10n_ve_currency_rate_outdated)

        invoice.refresh_invoice_currency_rate()
        invoice.invalidate_recordset(["l10n_ve_currency_rate_outdated"])
        self.assertFalse(invoice.l10n_ve_currency_rate_outdated)
