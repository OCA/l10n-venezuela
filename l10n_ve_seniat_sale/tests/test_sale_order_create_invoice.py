# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.l10n_ve_seniat.tests.common import L10nVeSeniatCommon


@tagged("post_install", "-at_install")
class TestSaleOrderCreateInvoice(L10nVeSeniatCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.journal = cls.company_data["default_journal_sale"]
        cls._l10n_ve_configure_journal_digital(cls.journal)

    def _create_ve_product(self, name, price):
        tmpl = self.env["product.template"].create(
            {
                "name": name,
                "company_id": self.env.company.id,
                "list_price": price,
                "standard_price": price / 2,
                "taxes_id": [(6, 0, [self.company_data["default_tax_sale"].id])],
                "supplier_taxes_id": [
                    (6, 0, [self.company_data["default_tax_purchase"].id])
                ],
            }
        )
        return tmpl.product_variant_ids[0]

    def _create_confirmed_ve_order(self):
        partner = self.env["res.partner"].create(
            {
                "name": "Cliente VE factura directa",
                "country_id": self.env.ref("base.ve").id,
                "vat": "J12345679",
            }
        )
        product = self._create_ve_product("Producto factura directa", 100.0)
        order = self.env["sale.order"].create(
            {
                "partner_id": partner.id,
                "journal_id": self.journal.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": product.id,
                            "product_uom_qty": 1,
                            "price_unit": 100.0,
                        },
                    )
                ],
            }
        )
        order.action_confirm()
        return order

    def test_create_invoice_without_wizard(self):
        order = self._create_confirmed_ve_order()
        action = order.action_l10n_ve_create_invoice()
        self.assertEqual(action.get("res_model"), "account.move")
        self.assertEqual(len(order.invoice_ids), 1)
        self.assertEqual(order.invoice_ids.move_type, "out_invoice")

    def test_wizard_blocks_advance_invoice(self):
        order = self._create_confirmed_ve_order()
        wizard = self.env["sale.advance.payment.inv"].create(
            {
                "sale_order_ids": order,
                "advance_payment_method": "percentage",
                "amount": 50.0,
            }
        )
        with self.assertRaises(UserError):
            wizard.create_invoices()

    def test_wizard_creates_regular_invoice_for_ve(self):
        order = self._create_confirmed_ve_order()
        wizard = self.env["sale.advance.payment.inv"].create(
            {
                "sale_order_ids": order,
                "advance_payment_method": "delivered",
            }
        )
        action = wizard.create_invoices()
        self.assertEqual(action.get("res_model"), "account.move")
        self.assertEqual(len(order.invoice_ids), 1)
