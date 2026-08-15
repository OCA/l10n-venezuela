# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import Command, fields
from odoo.exceptions import ValidationError
from odoo.tests import tagged

from odoo.addons.l10n_ve_loyalty.models import l10n_ve_global_discount as discount_logic
from odoo.addons.l10n_ve_seniat.tests.common import L10nVeSeniatCommon


@tagged("post_install", "-at_install")
class TestAccountMovePostDiscount(L10nVeSeniatCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner_ve = cls.env["res.partner"].create(
            {
                "name": "Partner VE post discount",
                "country_id": cls.env.ref("base.ve").id,
                "vat": "J12345680",
            }
        )
        cls.company_data["default_journal_sale"].write(
            {"l10n_ve_emission_medium": "free"}
        )
        cls.reason_early = cls.env.ref(
            "l10n_ve_loyalty.l10n_ve_discount_reason_early_payment",
            raise_if_not_found=False,
        )
        if not cls.reason_early:
            cls.reason_early = cls.env["l10n.ve.discount.reason"].create(
                {"name": "Pronto pago"}
            )

    def _create_posted_invoice(self, price_unit=1000.0, tax=True):
        tax_ids = []
        if tax:
            tax_ids = [self.company_data["default_tax_sale"].id]
        move = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner_ve.id,
                "invoice_date": fields.Date.today(),
                "invoice_line_ids": [
                    Command.create(
                        {
                            "name": "Product line",
                            "quantity": 1.0,
                            "price_unit": price_unit,
                            "account_id": self.company_data["default_account_revenue"].id,
                            "tax_ids": [Command.set(tax_ids)],
                        }
                    )
                ],
            }
        )
        move.action_post()
        move.l10n_ve_invoice_original_printed = True
        return move

    def _create_wizard(
        self,
        move,
        mode="percentage",
        percentage=0.1,
        amount=0.0,
        discount_currency=None,
    ):
        vals = {
            "move_id": move.id,
            "reason_id": self.reason_early.id,
            "discount_mode": mode,
            "discount_percentage": percentage,
            "amount": amount,
            "amount_base": "untaxed",
            "discount_currency_id": (discount_currency or move.currency_id).id,
        }
        return self.env["l10n.ve.account.move.discount.wizard"].create(vals)

    def test_post_discount_creates_draft_credit_note_percentage(self):
        invoice = self._create_posted_invoice(price_unit=1000.0)
        expected = invoice.currency_id.round(invoice.amount_untaxed * 0.1)
        wizard = self._create_wizard(invoice, mode="percentage", percentage=0.1)
        action = wizard.action_apply_discount()
        credit = self.env["account.move"].browse(action["res_id"])
        self.assertEqual(credit.state, "draft")
        self.assertEqual(credit.move_type, "out_refund")
        self.assertEqual(credit.reversed_entry_id, invoice)
        self.assertEqual(credit.l10n_ve_discount_reason_id, self.reason_early)
        self.assertAlmostEqual(credit.amount_untaxed, expected, places=2)
        self.assertTrue(credit.invoice_line_ids)
        self.assertTrue(credit.invoice_line_ids[0].tax_ids)

    def test_post_discount_creates_draft_credit_note_amount(self):
        invoice = self._create_posted_invoice(price_unit=1000.0)
        wizard = self._create_wizard(invoice, mode="amount", amount=250.0)
        action = wizard.action_apply_discount()
        credit = self.env["account.move"].browse(action["res_id"])
        self.assertEqual(credit.state, "draft")
        self.assertAlmostEqual(credit.amount_untaxed, 250.0, places=2)

    def test_post_discount_allows_multiple_credit_notes(self):
        invoice = self._create_posted_invoice(price_unit=1000.0)
        first = self._create_wizard(invoice, mode="amount", amount=100.0)
        first.action_apply_discount()
        second = self._create_wizard(invoice, mode="amount", amount=150.0)
        action = second.action_apply_discount()
        credit = self.env["account.move"].browse(action["res_id"])
        self.assertAlmostEqual(credit.amount_untaxed, 150.0, places=2)
        self.assertEqual(len(invoice._l10n_ve_post_discount_credit_notes()), 2)
        self.assertAlmostEqual(
            invoice._l10n_ve_post_discount_available_untaxed(),
            invoice.currency_id.round(invoice.amount_untaxed - 250.0),
            places=2,
        )

    def test_post_discount_cannot_exceed_available(self):
        invoice = self._create_posted_invoice(price_unit=100.0)
        wizard = self._create_wizard(
            invoice,
            mode="amount",
            amount=invoice.amount_untaxed + 50.0,
        )
        with self.assertRaises(ValidationError):
            wizard.action_apply_discount()

    def test_post_discount_blocked_on_draft_invoice(self):
        move = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner_ve.id,
                "invoice_line_ids": [
                    Command.create(
                        {
                            "name": "Product line",
                            "quantity": 1.0,
                            "price_unit": 100.0,
                            "account_id": self.company_data[
                                "default_account_revenue"
                            ].id,
                            "tax_ids": [
                                Command.set([self.company_data["default_tax_sale"].id])
                            ],
                        }
                    )
                ],
            }
        )
        action = move.action_l10n_ve_open_post_discount_wizard()
        self.assertEqual(action["res_model"], "l10n.ve.account.move.discount.wizard")

    def test_post_discount_split_amount_by_weights(self):
        invoice = self._create_posted_invoice()
        parts = invoice._l10n_ve_split_amount_by_weights(100.0, [800.0, 200.0])
        self.assertEqual(
            [invoice.currency_id.round(part) for part in parts],
            [80.0, 20.0],
        )
        prepared = invoice._l10n_ve_prepare_post_discount_credit_note_lines(
            100.0, self.reason_early
        )
        self.assertEqual(len(prepared), 1)
        self.assertAlmostEqual(prepared[0][2]["price_unit"], 100.0, places=2)

    def test_show_post_discount_action_on_posted_invoice(self):
        invoice = self._create_posted_invoice()
        self.assertTrue(invoice.l10n_ve_show_credit_note_action)
        self.assertTrue(invoice.l10n_ve_show_post_discount_action)

    def test_post_discount_usd_invoice_does_not_require_matching_lines(self):
        company_ccy = self.env.company.currency_id
        usd = self.env.ref("base.USD")
        foreign = usd if company_ccy != usd else self.env.ref("base.EUR")
        foreign.write({"active": True})
        journal = self.company_data["default_journal_sale"]
        journal.write({"l10n_ve_emission_medium": "free"})
        date_invoice = fields.Date.today()
        self.env["res.currency.rate"].create(
            {
                "currency_id": foreign.id,
                "company_id": self.env.company.id,
                "name": date_invoice,
                "inverse_company_rate": 2.0,
            }
        )
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner_ve.id,
                "journal_id": journal.id,
                "currency_id": foreign.id,
                "invoice_date": date_invoice,
                "invoice_line_ids": [
                    Command.create(
                        {
                            "name": "Product A",
                            "quantity": 1.0,
                            "price_unit": 80.0,
                            "account_id": self.company_data[
                                "default_account_revenue"
                            ].id,
                            "tax_ids": [
                                Command.set(
                                    [self.company_data["default_tax_sale"].id]
                                )
                            ],
                        }
                    ),
                    Command.create(
                        {
                            "name": "Product B",
                            "quantity": 1.0,
                            "price_unit": 20.0,
                            "account_id": self.company_data[
                                "default_account_revenue"
                            ].id,
                            "tax_ids": [
                                Command.set(
                                    [self.company_data["default_tax_sale"].id]
                                )
                            ],
                        }
                    ),
                ],
            }
        )
        invoice.action_post()
        invoice.l10n_ve_invoice_original_printed = True
        wizard = self._create_wizard(
            invoice, mode="amount", amount=10.0, discount_currency=foreign
        )
        action = wizard.action_apply_discount()
        credit = self.env["account.move"].browse(action["res_id"])
        self.assertEqual(credit.state, "draft")
        self.assertTrue(credit._l10n_ve_is_post_discount_credit_note())
        self.assertEqual(credit.currency_id, invoice.company_currency_id)
        expected_bs = invoice._l10n_ve_post_discount_amount_in_currency(
            10.0, invoice.company_currency_id
        )
        self.assertAlmostEqual(credit.amount_untaxed, expected_bs, places=2)
        self.assertNotEqual(len(credit.invoice_line_ids), len(invoice.invoice_line_ids))
        credit.action_post()
        self.assertEqual(credit.state, "posted")

    def test_post_discount_usd_keeps_foreign_currency_without_emission_medium(self):
        company_ccy = self.env.company.currency_id
        usd = self.env.ref("base.USD")
        foreign = usd if company_ccy != usd else self.env.ref("base.EUR")
        foreign.write({"active": True})
        journal = self.company_data["default_journal_sale"]
        journal.write({"l10n_ve_emission_medium": False})
        date_invoice = fields.Date.today()
        self.env["res.currency.rate"].create(
            {
                "currency_id": foreign.id,
                "company_id": self.env.company.id,
                "name": date_invoice,
                "inverse_company_rate": 2.0,
            }
        )
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner_ve.id,
                "journal_id": journal.id,
                "currency_id": foreign.id,
                "invoice_date": date_invoice,
                "invoice_line_ids": [
                    Command.create(
                        {
                            "name": "Product A",
                            "quantity": 1.0,
                            "price_unit": 100.0,
                            "account_id": self.company_data[
                                "default_account_revenue"
                            ].id,
                        }
                    )
                ],
            }
        )
        invoice.action_post()
        invoice.l10n_ve_invoice_original_printed = True
        wizard = self._create_wizard(
            invoice, mode="amount", amount=10.0, discount_currency=foreign
        )
        action = wizard.action_apply_discount()
        credit = self.env["account.move"].browse(action["res_id"])
        self.assertEqual(credit.currency_id, foreign)
        self.assertAlmostEqual(credit.amount_untaxed, 10.0, places=2)

    def test_post_discount_fixed_amount_in_company_currency(self):
        company_ccy = self.env.company.currency_id
        usd = self.env.ref("base.USD")
        foreign = usd if company_ccy != usd else self.env.ref("base.EUR")
        foreign.write({"active": True})
        journal = self.company_data["default_journal_sale"]
        journal.write({"l10n_ve_emission_medium": "free"})
        date_invoice = fields.Date.today()
        self.env["res.currency.rate"].create(
            {
                "currency_id": foreign.id,
                "company_id": self.env.company.id,
                "name": date_invoice,
                "inverse_company_rate": 2.0,
            }
        )
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner_ve.id,
                "journal_id": journal.id,
                "currency_id": foreign.id,
                "invoice_date": date_invoice,
                "invoice_line_ids": [
                    Command.create(
                        {
                            "name": "Product A",
                            "quantity": 1.0,
                            "price_unit": 100.0,
                            "account_id": self.company_data[
                                "default_account_revenue"
                            ].id,
                        }
                    )
                ],
            }
        )
        invoice.action_post()
        invoice.l10n_ve_invoice_original_printed = True
        amount_bs = invoice._l10n_ve_post_discount_amount_in_currency(
            10.0, invoice.company_currency_id
        )
        wizard = self._create_wizard(
            invoice,
            mode="amount",
            amount=amount_bs,
            discount_currency=invoice.company_currency_id,
        )
        action = wizard.action_apply_discount()
        credit = self.env["account.move"].browse(action["res_id"])
        self.assertEqual(credit.currency_id, invoice.company_currency_id)
        self.assertAlmostEqual(credit.amount_untaxed, amount_bs, places=2)
        self.assertAlmostEqual(
            invoice._l10n_ve_credit_untaxed_in_invoice_currency(credit),
            10.0,
            places=2,
        )

    def test_post_discount_keeps_entered_company_currency_untaxed(self):
        company_ccy = self.env.company.currency_id
        usd = self.env.ref("base.USD")
        foreign = usd if company_ccy != usd else self.env.ref("base.EUR")
        foreign.write({"active": True})
        journal = self.company_data["default_journal_sale"]
        journal.write({"l10n_ve_emission_medium": "free"})
        date_invoice = fields.Date.today()
        self.env["res.currency.rate"].create(
            {
                "currency_id": foreign.id,
                "company_id": self.env.company.id,
                "name": date_invoice,
                "inverse_company_rate": 2.0,
            }
        )
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner_ve.id,
                "journal_id": journal.id,
                "currency_id": foreign.id,
                "invoice_date": date_invoice,
                "invoice_line_ids": [
                    Command.create(
                        {
                            "name": "Product A",
                            "quantity": 1.0,
                            "price_unit": 100.0,
                            "account_id": self.company_data[
                                "default_account_revenue"
                            ].id,
                        }
                    )
                ],
            }
        )
        invoice.action_post()
        invoice.l10n_ve_invoice_original_printed = True
        wizard = self._create_wizard(
            invoice,
            mode="amount",
            amount=100.0,
            discount_currency=invoice.company_currency_id,
        )
        action = wizard.action_apply_discount()
        credit = self.env["account.move"].browse(action["res_id"])
        self.assertEqual(credit.currency_id, invoice.company_currency_id)
        self.assertAlmostEqual(credit.amount_untaxed, 100.0, places=2)

    def test_post_discount_fixed_amount_on_total_uses_same_base_as_draft(self):
        invoice = self._create_posted_invoice(price_unit=100.0)
        tax = self.company_data["default_tax_sale"]
        tax_factor = 1.0 + (tax.amount / 100.0)
        amount_total = invoice.currency_id.round(10.0 * tax_factor)
        wizard = self.env["l10n.ve.account.move.discount.wizard"].create(
            {
                "move_id": invoice.id,
                "reason_id": self.reason_early.id,
                "discount_mode": "amount",
                "amount_base": "total",
                "amount": amount_total,
                "discount_currency_id": invoice.currency_id.id,
            }
        )
        expected_available = invoice._l10n_ve_discount_available_in_currency(
            "total", invoice.currency_id
        )
        self.assertAlmostEqual(wizard.available_amount, expected_available, places=2)
        self.assertAlmostEqual(expected_available, invoice.amount_total, places=2)
        company_wizard = self.env["l10n.ve.account.move.discount.wizard"].create(
            {
                "move_id": invoice.id,
                "reason_id": self.reason_early.id,
                "discount_mode": "amount",
                "amount_base": "total",
                "discount_currency_id": invoice.company_currency_id.id,
            }
        )
        self.assertAlmostEqual(
            company_wizard.available_amount,
            abs(invoice.amount_total_signed),
            places=2,
        )
        remaining = invoice._l10n_ve_discount_remaining_subtotal_by_taxes()
        expected_untaxed = discount_logic.l10n_ve_fixed_discount_to_untaxed(
            invoice, amount_total, "total", remaining
        )
        action = wizard.action_apply_discount()
        credit = self.env["account.move"].browse(action["res_id"])
        self.assertAlmostEqual(credit.amount_untaxed, expected_untaxed, delta=0.02)
