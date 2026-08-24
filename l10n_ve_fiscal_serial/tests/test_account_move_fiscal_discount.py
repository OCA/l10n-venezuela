# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import Command
from odoo.tests import tagged

from odoo.addons.l10n_ve_seniat.tests.common import L10nVeSeniatCommon


@tagged("post_install", "-at_install")
class TestAccountMoveFiscalDiscount(L10nVeSeniatCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        discount_group = cls.env.ref(
            "l10n_ve_loyalty.group_l10n_ve_global_discount",
            raise_if_not_found=False,
        )
        if discount_group:
            cls.env.user.groups_id = [Command.link(discount_group.id)]
        cls.partner_ve = cls.env["res.partner"].create(
            {
                "name": "Partner fiscal discount",
                "country_id": cls.env.ref("base.ve").id,
                "vat": "J12345678",
            }
        )

    def _require_loyalty_discounts(self):
        if "l10n.ve.discount.reason" not in self.env:
            self.skipTest("Requires l10n_ve_loyalty for global discounts")
        if "l10n.ve.account.move.discount" not in self.env:
            self.skipTest("Requires l10n_ve_loyalty for global discounts")

    def _create_invoice(self, discount=0.0):
        product = self._create_product(
            name="Product line",
            list_price=100.0,
            taxes_id=[Command.set(self.company_data["default_tax_sale"].ids)],
        )
        return self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner_ve.id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": product.id,
                            "name": "Product line",
                            "quantity": 1.0,
                            "price_unit": 100.0,
                            "discount": discount,
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

    def test_fiscal_payload_line_discount_amount(self):
        move = self._create_invoice(discount=10.0)
        lines = move._l10n_ve_fiscal_serial_invoice_lines_payload()
        self.assertEqual(len(lines), 1)
        line = lines[0]
        self.assertAlmostEqual(line["discount"], 10.0, places=2)
        self.assertGreater(line["discount_amount"], 0.0)
        self.assertAlmostEqual(line["discount_amount"], 10.0, places=2)
        tax_totals = move.tax_totals
        if "l10n_ve_line_discount_amount" in tax_totals:
            self.assertAlmostEqual(
                line["discount_amount"],
                tax_totals["l10n_ve_line_discount_amount"],
                places=2,
            )

    def test_fiscal_payload_without_line_discount(self):
        move = self._create_invoice(discount=0.0)
        lines = move._l10n_ve_fiscal_serial_invoice_lines_payload()
        self.assertEqual(len(lines), 1)
        self.assertAlmostEqual(lines[0]["discount_amount"], 0.0, places=2)

    def _get_discount_reason(self):
        self._require_loyalty_discounts()
        reason = self.env["l10n.ve.discount.reason"].search([], limit=1)
        if not reason:
            reason = self.env["l10n.ve.discount.reason"].create({"name": "Descuento"})
        return reason

    def test_fiscal_payload_keeps_gross_price_with_global_discount(self):
        self._require_loyalty_discounts()
        move = self._create_invoice(discount=10.0)
        reason = self._get_discount_reason()
        self.env["l10n.ve.account.move.discount"].create(
            {
                "move_id": move.id,
                "reason_id": reason.id,
                "amount": 9.0,
                "discount_type": "percentage",
                "discount_percentage": 0.1,
            }
        )
        lines = move._l10n_ve_fiscal_serial_invoice_lines_payload()
        self.assertAlmostEqual(lines[0]["price_unit"], 100.0, places=2)
        self.assertAlmostEqual(lines[0]["discount"], 10.0, places=2)

    def test_fiscal_payload_includes_global_discount_amount(self):
        self._require_loyalty_discounts()
        move = self._create_invoice(discount=0.0)
        reason = self._get_discount_reason()
        self.env["l10n.ve.account.move.discount"].create(
            {
                "move_id": move.id,
                "reason_id": reason.id,
                "amount": 10.0,
                "discount_type": "fixed",
            }
        )
        payload = move._l10n_ve_fiscal_serial_base_payload()
        self.assertAlmostEqual(payload["global_discount_amount"], 10.0, places=2)
        tax_totals = move.tax_totals
        self.assertAlmostEqual(
            payload["global_discount_amount"],
            tax_totals["l10n_ve_global_discount_amount"],
            places=2,
        )

    def test_fiscal_payload_global_discount_on_total_sends_untaxed(self):
        """TFHKA aplica q- sobre el subtotal: enviar la base imponible equivalente."""
        self._require_loyalty_discounts()
        move = self._create_invoice(discount=0.0)
        tax = self.company_data["default_tax_sale"]
        self.assertAlmostEqual(tax.amount, 16.0, places=2)
        wizard = self.env["l10n.ve.account.move.discount.wizard"].create(
            {
                "move_id": move.id,
                "discount_mode": "amount",
                "amount_base": "total",
                "amount": 10.0,
                "reason_id": self._get_discount_reason().id,
            }
        )
        wizard.action_apply_discount()
        expected_untaxed = move.currency_id.round(10.0 / 1.16)
        self.assertAlmostEqual(
            move.l10n_ve_global_discount_ids.amount, expected_untaxed, places=2
        )
        payload = move._l10n_ve_fiscal_serial_base_payload()
        self.assertAlmostEqual(
            payload["global_discount_amount"], expected_untaxed, places=2
        )
        self.assertNotAlmostEqual(payload["global_discount_amount"], 10.0, places=2)
