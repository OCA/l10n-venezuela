# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.l10n_ve_seniat.tests.common import L10nVeSeniatCommon


@tagged("post_install", "-at_install")
class TestSaleOrderConfirm(L10nVeSeniatCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.journal = cls.company_data["default_journal_sale"]
        cls._l10n_ve_configure_journal_digital(cls.journal)

    def _create_ve_product(
        self, name="Producto confirmación", price=100.0, service=False
    ):
        vals = {
            "name": name,
            "company_id": self.env.company.id,
            "list_price": price,
            "standard_price": price / 2,
            "taxes_id": [(6, 0, [self.company_data["default_tax_sale"].id])],
            "supplier_taxes_id": [
                (6, 0, [self.company_data["default_tax_purchase"].id])
            ],
        }
        if service:
            vals["type"] = "service"
            vals["invoice_policy"] = "order"
        tmpl = self.env["product.template"].create(vals)
        return tmpl.product_variant_ids[0]

    def _create_ve_order(self, qty, service=False):
        partner = self.env["res.partner"].create(
            {
                "name": "Cliente VE confirmación",
                "country_id": self.env.ref("base.ve").id,
                "vat": "J12345680",
            }
        )
        product = self._create_ve_product(service=service)
        return self.env["sale.order"].create(
            {
                "partner_id": partner.id,
                "journal_id": self.journal.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": product.id,
                            "product_uom_qty": qty,
                            "price_unit": 100.0,
                        },
                    )
                ],
            }
        )

    def test_confirm_rejects_zero_quantity(self):
        order = self._create_ve_order(qty=0.0)
        with self.assertRaises(UserError):
            order.action_confirm()

    def test_confirm_rejects_negative_quantity(self):
        order = self._create_ve_order(qty=-1.0)
        with self.assertRaises(UserError):
            order.action_confirm()

    def test_confirm_allows_quantity_change_after_confirmation(self):
        # Service product: sale_stock does not block qty below delivered.
        order = self._create_ve_order(qty=1.0, service=True)
        order.action_confirm()
        order.order_line.product_uom_qty = 0.0
        self.assertEqual(order.order_line.product_uom_qty, 0.0)
        order.order_line.product_uom_qty = -2.0
        self.assertEqual(order.order_line.product_uom_qty, -2.0)
