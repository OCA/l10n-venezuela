# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests import tagged

from odoo.addons.l10n_ve_seniat.tests.common import L10nVeSeniatCommon


@tagged("post_install", "-at_install")
class TestSaleOrderLineVe(L10nVeSeniatCommon):
    def _create_ve_product(self):
        tmpl = self.env["product.template"].create(
            {
                "name": "SO línea precio VE",
                "company_id": self.env.company.id,
                "list_price": 100.0,
                "standard_price": 50.0,
                "taxes_id": [(6, 0, [self.company_data["default_tax_sale"].id])],
                "supplier_taxes_id": [
                    (6, 0, [self.company_data["default_tax_purchase"].id])
                ],
            }
        )
        return tmpl.product_variant_ids[0]

    def test_ve_sale_line_rejects_non_positive_price(self):
        partner = self.env["res.partner"].create(
            {
                "name": "Cliente VE",
                "country_id": self.env.ref("base.ve").id,
            }
        )
        product = self._create_ve_product()
        with self.assertRaises(ValidationError) as cm:
            self.env["sale.order"].create(
                {
                    "partner_id": partner.id,
                    "order_line": [
                        (
                            0,
                            0,
                            {
                                "product_id": product.id,
                                "product_uom_qty": 1,
                                "price_unit": 0.0,
                            },
                        )
                    ],
                }
            )
        self.assertIn("precio menor o igual a cero", str(cm.exception))

    def test_ve_sale_line_rejects_100_percent_discount(self):
        partner = self.env["res.partner"].create(
            {
                "name": "Cliente VE desc",
                "country_id": self.env.ref("base.ve").id,
            }
        )
        product = self._create_ve_product()
        with self.assertRaises(ValidationError) as cm:
            self.env["sale.order"].create(
                {
                    "partner_id": partner.id,
                    "order_line": [
                        (
                            0,
                            0,
                            {
                                "product_id": product.id,
                                "product_uom_qty": 1,
                                "price_unit": 100.0,
                                "discount": 100.0,
                            },
                        )
                    ],
                }
            )
        self.assertIn("100%", str(cm.exception))

    def test_ve_sale_discount_wizard_rejects_100_percent_global(self):
        partner = self.env["res.partner"].create(
            {
                "name": "Cliente VE wizard",
                "country_id": self.env.ref("base.ve").id,
            }
        )
        product = self._create_ve_product()
        order = self.env["sale.order"].create(
            {
                "partner_id": partner.id,
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
        wizard = self.env["sale.order.discount"].create(
            {
                "sale_order_id": order.id,
                "discount_type": "so_discount",
                "discount_percentage": 1.0,
            }
        )
        with self.assertRaises(ValidationError) as cm:
            wizard.action_apply_discount()
        self.assertIn("100%", str(cm.exception))

    def test_ve_sale_line_negative_ok_for_company_discount_product(self):
        partner = self.env["res.partner"].create(
            {
                "name": "Cliente VE 2",
                "country_id": self.env.ref("base.ve").id,
            }
        )
        product = self._create_ve_product()
        self.env.company.sale_discount_product_id = product
        order = self.env["sale.order"].create(
            {
                "partner_id": partner.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": product.id,
                            "product_uom_qty": 1,
                            "price_unit": -25.0,
                        },
                    )
                ],
            }
        )
        line = order.order_line.filtered(lambda sol: not sol.display_type)
        self.assertEqual(len(line), 1)
        self.assertLess(line.price_unit, 0)

    def test_ve_invoice_negative_price_ok_for_company_discount_product(self):
        partner = self.env["res.partner"].create(
            {
                "name": "Cliente VE factura descuento",
                "country_id": self.env.ref("base.ve").id,
                "vat": "J12345678",
            }
        )
        product = self._create_ve_product()
        self.env.company.sale_discount_product_id = product
        move = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": partner.id,
                "invoice_date": fields.Date.today(),
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": product.id,
                            "name": "Descuento",
                            "quantity": 1.0,
                            "price_unit": -50.0,
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
        line = move.invoice_line_ids.filtered(lambda aml: aml.display_type == "product")
        self.assertEqual(len(line), 1)
        self.assertLess(line.price_unit, 0)
