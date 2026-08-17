# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import Command, fields
from odoo.exceptions import ValidationError
from odoo.tests import tagged

from .common import L10nVeSeniatCommon


@tagged("post_install", "-at_install")
class TestAccountMoveLine(L10nVeSeniatCommon):
    def test_validate_price_not_zero_raises_on_zero_price(self):
        partner = self.env["res.partner"].create(
            {
                "name": "Partner",
                "country_id": self.env.ref("base.ve").id,
                "vat": "J12345678",
            }
        )
        with self.assertRaises(ValidationError) as cm:
            self.env["account.move"].create(
                {
                    "move_type": "out_invoice",
                    "partner_id": partner.id,
                    "invoice_line_ids": [
                        (
                            0,
                            0,
                            {
                                "name": "Zero price line",
                                "quantity": 1.0,
                                "price_unit": 0.0,
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
        self.assertIn("precio menor o igual a cero", str(cm.exception))

    def test_ve_invoice_line_rejects_100_percent_discount(self):
        partner = self.env["res.partner"].create(
            {
                "name": "Partner desc",
                "country_id": self.env.ref("base.ve").id,
                "vat": "J12345678",
            }
        )
        with self.assertRaises(ValidationError) as cm:
            self.env["account.move"].create(
                {
                    "move_type": "out_invoice",
                    "partner_id": partner.id,
                    "invoice_line_ids": [
                        (
                            0,
                            0,
                            {
                                "name": "Línea con descuento total",
                                "quantity": 1.0,
                                "price_unit": 100.0,
                                "discount": 100.0,
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
        self.assertIn("100%", str(cm.exception))

    def test_subtotal_company_currency_invoice(self):
        partner = self.env["res.partner"].create(
            {
                "name": "Partner",
                "country_id": self.env.ref("base.ve").id,
                "vat": "J12345678",
            }
        )
        move = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": partner.id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Line",
                            "quantity": 2.0,
                            "price_unit": 100.0,
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
        move.action_post()
        line = move.line_ids.filtered(lambda aml: aml.display_type == "product")
        self.assertEqual(len(line), 1)
        self.assertGreater(line.subtotal_company_currency, 0)

    def test_put_unique_tax_per_line_purchase_adds_default_tax(self):
        supplier = self.env["res.partner"].create(
            {
                "name": "Supplier",
                "country_id": self.env.ref("base.ve").id,
                "vat": "J98765432",
            }
        )
        move = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": supplier.id,
                "invoice_date": fields.Date.today(),
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Line no tax",
                            "quantity": 1.0,
                            "price_unit": 50.0,
                            "account_id": self.company_data[
                                "default_account_expense"
                            ].id,
                            "tax_ids": [],
                        },
                    )
                ],
            }
        )
        line = move.invoice_line_ids.filtered(lambda aml: aml.display_type == "product")
        self.assertEqual(len(line.tax_ids), 1)
        self.assertEqual(line.tax_ids, self.company_data["default_tax_purchase"])

    def test_vendor_bill_keeps_selected_tax_without_product(self):
        supplier = self.env["res.partner"].create(
            {
                "name": "Supplier tax free line",
                "country_id": self.env.ref("base.ve").id,
                "vat": "J87654321",
            }
        )
        purchase_tax = self.company_data["default_tax_purchase"]
        move = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": supplier.id,
                "invoice_date": fields.Date.today(),
                "invoice_line_ids": [
                    Command.create(
                        {
                            "name": "Servicio sin producto",
                            "quantity": 1.0,
                            "price_unit": 100.0,
                            "account_id": self.company_data[
                                "default_account_expense"
                            ].id,
                            "tax_ids": [Command.set([purchase_tax.id])],
                        }
                    )
                ],
            }
        )
        line = move.invoice_line_ids.filtered(lambda aml: aml.display_type == "product")
        self.assertFalse(line.product_id)
        self.assertEqual(line.tax_ids, purchase_tax)
        line.write({"tax_ids": [Command.set([purchase_tax.id])]})
        self.assertEqual(line.tax_ids, purchase_tax)
        self.assertFalse(line._l10n_ve_must_use_exempt_tax())

    def test_subtotal_refund(self):
        partner = self.env["res.partner"].create(
            {"name": "P", "country_id": self.env.ref("base.ve").id, "vat": "J12345678"}
        )
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": partner.id,
                "invoice_date": fields.Date.today(),
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Line",
                            "quantity": 1.0,
                            "price_unit": 50.0,
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
        invoice.action_post()
        invoice.l10n_ve_invoice_original_printed = True
        move = invoice._reverse_moves()
        move.action_post()
        line = move.line_ids.filtered(lambda aml: aml.display_type == "product")
        self.assertGreater(line.subtotal_company_currency, 0)

    def test_subtotal_company_currency_entry_is_zero(self):
        move = self.env["account.move"].create(
            {
                "move_type": "entry",
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "d",
                            "account_id": self.company_data[
                                "default_account_revenue"
                            ].id,
                            "debit": 5.0,
                            "credit": 0.0,
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "name": "c",
                            "account_id": self.company_data[
                                "default_account_expense"
                            ].id,
                            "debit": 0.0,
                            "credit": 5.0,
                        },
                    ),
                ],
            }
        )
        move.action_post()
        line = move.line_ids.filtered(lambda aml: aml.debit > 0)
        self.assertEqual(len(line), 1)
        self.assertEqual(line.subtotal_company_currency, 0.0)

    def test_entry_lines_skip_ve_validations_on_write(self):
        move = self.env["account.move"].create(
            {
                "move_type": "entry",
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "d",
                            "account_id": self.company_data[
                                "default_account_revenue"
                            ].id,
                            "debit": 1.0,
                            "credit": 0.0,
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "name": "c",
                            "account_id": self.company_data[
                                "default_account_expense"
                            ].id,
                            "debit": 0.0,
                            "credit": 1.0,
                        },
                    ),
                ],
            }
        )
        line = move.line_ids.filtered(lambda aml: aml.debit > 0)
        line.write({"name": "asiento ok"})
        self.assertEqual(line.name, "asiento ok")

    def test_l10n_ve_report_invoice_lines_discount_last(self):
        if "sale_discount_product_id" not in self.env.company._fields:
            self.skipTest("sale_discount_product_id requires l10n_ve_loyalty")
        partner = self.env["res.partner"].create(
            {
                "name": "Partner report",
                "country_id": self.env.ref("base.ve").id,
                "vat": "J12345680",
            }
        )
        product = self.env["product.product"].create(
            {
                "name": "Producto reporte",
                "list_price": 100.0,
                "taxes_id": [(6, 0, [self.company_data["default_tax_sale"].id])],
            }
        )
        self.env.company.sale_discount_product_id = product
        move = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": partner.id,
                "invoice_line_ids": [
                    Command.create(
                        {
                            "product_id": product.id,
                            "name": "Descuento",
                            "quantity": 1.0,
                            "price_unit": -10.0,
                            "account_id": self.company_data["default_account_revenue"].id,
                            "tax_ids": [(6, 0, [self.company_data["default_tax_sale"].id])],
                            "sequence": 5,
                        }
                    ),
                    Command.create(
                        {
                            "name": "Producto",
                            "quantity": 1.0,
                            "price_unit": 100.0,
                            "account_id": self.company_data["default_account_revenue"].id,
                            "tax_ids": [(6, 0, [self.company_data["default_tax_sale"].id])],
                            "sequence": 10,
                        }
                    ),
                ],
            }
        )
        report_lines = move.l10n_ve_report_invoice_lines()
        product_lines = report_lines.filtered(lambda aml: aml.display_type == "product")
        self.assertEqual(product_lines[-1].product_id, product)

    def test_report_line_description_marks_exempt_product(self):
        partner = self.env["res.partner"].create(
            {
                "name": "Partner exento",
                "country_id": self.env.ref("base.ve").id,
                "vat": "J12345678",
            }
        )
        exempt_tax = self.env["product.template"]._l10n_ve_get_exent_sale_tax(
            self.env.company
        )
        self.assertTrue(exempt_tax)
        move = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": partner.id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Producto exento",
                            "quantity": 1.0,
                            "price_unit": 100.0,
                            "account_id": self.company_data[
                                "default_account_revenue"
                            ].id,
                            "tax_ids": [(6, 0, [exempt_tax.id])],
                        },
                    )
                ],
            }
        )
        line = move.invoice_line_ids.filtered(
            lambda aml: aml.display_type == "product"
        )
        line.ensure_one()
        self.assertEqual(line.l10n_ve_report_line_description(), "Producto exento (E)")
