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
            cls.journal, l10n_ve_max_invoice_lines=1
        )
        discount_group = cls.env.ref(
            "pba_discount_management.group_pba_global_sale_invoice_discount",
            raise_if_not_found=False,
        )
        if discount_group:
            cls.env.user.groups_id = [(4, discount_group.id)]

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
        journal.l10n_ve_emission_medium = "fiscal_machine"
        journal.l10n_ve_max_invoice_lines = 1
        order = self.env["sale.order"].new({"journal_id": journal.id})
        self.assertEqual(order._l10n_ve_get_max_invoice_lines_from_book(), 0)

    def test_global_discount_split_proportional_to_invoice_subtotal(self):
        partner = self.env["res.partner"].create(
            {
                "name": "Cliente VE split desc",
                "country_id": self.env.ref("base.ve").id,
                "vat": "J12345679",
            }
        )
        product_a = self._create_ve_product("Producto A", 1000.0)
        product_b = self._create_ve_product("Producto B", 100.0)
        order = self.env["sale.order"].create(
            {
                "partner_id": partner.id,
                "journal_id": self.journal.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": product_a.id,
                            "product_uom_qty": 1,
                            "price_unit": 1000.0,
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "product_id": product_b.id,
                            "product_uom_qty": 1,
                            "price_unit": 100.0,
                        },
                    ),
                ],
            }
        )
        wizard = self.env["sale.order.discount"].create(
            {
                "sale_order_id": order.id,
                "discount_type": "so_discount",
                "discount_percentage": 0.1,
            }
        )
        wizard.action_apply_discount()
        self.assertEqual(len(order.l10n_ve_global_discount_ids), 1)
        self.assertAlmostEqual(order.l10n_ve_global_discount_ids.amount, 110.0, places=2)
        order.action_confirm()
        invoices = order._create_invoices()
        self.assertEqual(len(invoices), 2)
        discount_lines = invoices.invoice_line_ids.filtered(
            lambda aml: aml.product_id == order.company_id.sale_discount_product_id
        )
        self.assertFalse(discount_lines)
        move_discounts = invoices.l10n_ve_global_discount_ids
        self.assertEqual(len(move_discounts), 2)
        discount_amounts = sorted(move_discounts.mapped("amount"))
        self.assertEqual(discount_amounts, [10.0, 100.0])
        self.assertAlmostEqual(sum(discount_amounts), 110.0, places=2)
        self.assertAlmostEqual(
            sum(invoices.mapped("amount_total")),
            order.amount_total,
            places=2,
        )

    def test_global_discount_transferred_on_single_invoice(self):
        partner = self.env["res.partner"].create(
            {
                "name": "Cliente VE desc simple",
                "country_id": self.env.ref("base.ve").id,
                "vat": "J12345681",
            }
        )
        product = self._create_ve_product("Producto desc", 100.0)
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
                    ),
                ],
            }
        )
        wizard = self.env["sale.order.discount"].create(
            {
                "sale_order_id": order.id,
                "discount_type": "so_discount",
                "discount_percentage": 0.1,
            }
        )
        wizard.action_apply_discount()
        order.action_confirm()
        invoice = order._create_invoices()
        self.assertEqual(len(invoice), 1)
        self.assertEqual(len(invoice.l10n_ve_global_discount_ids), 1)
        self.assertAlmostEqual(invoice.l10n_ve_global_discount_ids.amount, 10.0, places=2)
        self.assertAlmostEqual(invoice.amount_total, order.amount_total, places=2)

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
