# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests import tagged

from odoo.addons.l10n_ve_seniat.tests.common import L10nVeSeniatCommon


@tagged("post_install", "-at_install")
class TestSaleOrderInvoiceSplitDiscount(L10nVeSeniatCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.book = cls.env["account.book"].search(
            [("company_id", "=", cls.env.company.id)], limit=1
        )
        cls.book.l10n_ve_max_invoice_lines = 1
        cls.journal = cls.company_data["default_journal_sale"]
        cls._l10n_ve_configure_journal_digital(
            cls.journal,
            l10n_ve_limit_invoice_lines=True,
            l10n_ve_max_invoice_lines=1,
        )

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

    def test_fiscal_machine_journal_has_no_invoice_line_limit(self):
        journal = self.company_data["default_journal_sale"]
        self._l10n_ve_configure_journal_fiscal_machine(
            journal,
            l10n_ve_max_invoice_lines=1,
        )
        order = self.env["sale.order"].new({"journal_id": journal.id})
        self.assertEqual(order._l10n_ve_get_max_invoice_lines_from_book(), 0)

    def test_fix_discount_invoicing_rounding_after_invoice_legacy(self):
        partner = self.env["res.partner"].create(
            {
                "name": "Cliente VE redondeo desc",
                "country_id": self.env.ref("base.ve").id,
                "vat": "J12345680",
            }
        )
        product = self._create_ve_product("Producto redondeo", 4.73)
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
                            "price_unit": 4.73,
                        },
                    ),
                ],
            }
        )
        discount_product = order.company_id.sale_discount_product_id
        if not discount_product:
            discount_product = self.env["product.product"].create(
                {
                    "name": "Discount",
                    "type": "service",
                    "list_price": 0.0,
                    "company_id": order.company_id.id,
                }
            )
            order.company_id.sale_discount_product_id = discount_product
        self.env["sale.order.line"].create(
            {
                "order_id": order.id,
                "product_id": discount_product.id,
                "product_uom_qty": 1,
                "price_unit": -0.473,
                "tax_id": [(6, 0, [self.company_data["default_tax_sale"].id])],
            }
        )
        order.action_confirm()
        order._create_invoices()
        discount_line = order.order_line.filtered(
            lambda line: line.product_id == discount_product
        )
        self.assertGreater(discount_line.qty_to_invoice, 0.0)
        order.action_l10n_ve_fix_discount_invoicing_rounding()
        self.assertEqual(discount_line.qty_invoiced, discount_line.product_uom_qty)
        self.assertEqual(discount_line.qty_to_invoice, 0.0)
        self.assertEqual(order.invoice_status, "invoiced")
