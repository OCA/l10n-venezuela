# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import Command, fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

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

    def _create_wizard(self, move, mode="percentage", percentage=0.1, amount=0.0):
        return self.env["l10n.ve.account.move.post.discount.wizard"].create(
            {
                "move_id": move.id,
                "reason_id": self.reason_early.id,
                "discount_mode": mode,
                "discount_percentage": percentage,
                "amount": amount,
                "available_untaxed_amount": move._l10n_ve_post_discount_available_untaxed(),
            }
        )

    def test_post_discount_creates_draft_credit_note_percentage(self):
        invoice = self._create_posted_invoice(price_unit=1000.0)
        expected = invoice.currency_id.round(invoice.amount_untaxed * 0.1)
        wizard = self._create_wizard(invoice, mode="percentage", percentage=0.1)
        action = wizard.action_create_credit_note()
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
        action = wizard.action_create_credit_note()
        credit = self.env["account.move"].browse(action["res_id"])
        self.assertEqual(credit.state, "draft")
        self.assertAlmostEqual(credit.amount_untaxed, 250.0, places=2)

    def test_post_discount_allows_multiple_credit_notes(self):
        invoice = self._create_posted_invoice(price_unit=1000.0)
        first = self._create_wizard(invoice, mode="amount", amount=100.0)
        first.action_create_credit_note()
        second = self._create_wizard(invoice, mode="amount", amount=150.0)
        action = second.action_create_credit_note()
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
            wizard.action_create_credit_note()

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
        with self.assertRaises(UserError):
            move.action_l10n_ve_open_post_discount_wizard()

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
