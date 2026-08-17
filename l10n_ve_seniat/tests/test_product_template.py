# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import Command
from odoo.exceptions import ValidationError
from odoo.tests import tagged

from odoo.addons.l10n_ve_seniat.tests.common import L10nVeSeniatCommon


@tagged("post_install", "-at_install")
class TestProductTemplateL10nVe(L10nVeSeniatCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.sale_tax = cls.company_data["default_tax_sale"]
        cls.purchase_tax = cls.company_data["default_tax_purchase"]
        cls.sale_tax_b = cls.env["account.tax"].create(
            {
                "name": "IVA Venta B VE Test",
                "amount": 8.0,
                "amount_type": "percent",
                "type_tax_use": "sale",
                "company_id": cls.env.company.id,
            }
        )
        cls.purchase_tax_b = cls.env["account.tax"].create(
            {
                "name": "IVA Compra B VE Test",
                "amount": 5.0,
                "amount_type": "percent",
                "type_tax_use": "purchase",
                "company_id": cls.env.company.id,
            }
        )

    def _create_product_vals(self, **extra):
        base = {
            "name": "Product VE tax test",
            "company_id": self.env.company.id,
            "list_price": 100.0,
            "standard_price": 50.0,
            "taxes_id": [(6, 0, [self.sale_tax.id])],
            "supplier_taxes_id": [(6, 0, [self.purchase_tax.id])],
        }
        base.update(extra)
        return base

    def test_ve_product_requires_one_sale_tax(self):
        with self.assertRaises(ValidationError):
            self.env["product.template"].with_context(
                l10n_ve_skip_auto_exent_taxes=True
            ).create(self._create_product_vals(taxes_id=[(6, 0, [])]))

    def test_ve_product_requires_one_purchase_tax(self):
        with self.assertRaises(ValidationError):
            self.env["product.template"].with_context(
                l10n_ve_skip_auto_exent_taxes=True
            ).create(self._create_product_vals(supplier_taxes_id=[(6, 0, [])]))

    def test_ve_product_rejects_multiple_sale_taxes(self):
        with self.assertRaises(ValidationError):
            self.env["product.template"].create(
                self._create_product_vals(
                    taxes_id=[(6, 0, [self.sale_tax.id, self.sale_tax_b.id])]
                )
            )

    def test_ve_shared_product_allows_one_sale_tax_per_company(self):
        other_data = self.setup_other_company(
            name="VE Other Co Tax Test",
            account_fiscal_country_id=self.env.ref("base.ve").id,
        )
        other_sale = other_data["default_tax_sale"]
        other_purchase = other_data["default_tax_purchase"]
        self.assertTrue(other_sale)
        self.assertTrue(other_purchase)
        product = self.env["product.template"].create(
            {
                "name": "Shared VE product multi-company taxes",
                "company_id": False,
                "list_price": 100.0,
                "standard_price": 50.0,
                "taxes_id": [(6, 0, [self.sale_tax.id, other_sale.id])],
                "supplier_taxes_id": [
                    (6, 0, [self.purchase_tax.id, other_purchase.id])
                ],
            }
        )
        self.assertEqual(
            product.taxes_id.filtered(lambda t: t.company_id == self.env.company),
            self.sale_tax,
        )
        self.assertEqual(
            product.taxes_id.filtered(
                lambda t: t.company_id == other_data["company"]
            ),
            other_sale,
        )

    def test_ve_product_rejects_multiple_purchase_taxes(self):
        with self.assertRaises(ValidationError):
            self.env["product.template"].create(
                self._create_product_vals(
                    supplier_taxes_id=[
                        (6, 0, [self.purchase_tax.id, self.purchase_tax_b.id])
                    ]
                )
            )

    def test_ve_product_one_each_ok(self):
        p = self.env["product.template"].create(self._create_product_vals())
        self.assertEqual(len(p.taxes_id), 1)
        self.assertEqual(len(p.supplier_taxes_id), 1)

    def test_ve_product_tax_utility_fields_fill_original_taxes(self):
        p = self.env["product.template"].create(
            self._create_product_vals(
                l10n_ve_sale_tax_id=self.sale_tax_b.id,
                l10n_ve_purchase_tax_id=self.purchase_tax_b.id,
            )
        )
        self.assertEqual(p.taxes_id, self.sale_tax_b)
        self.assertEqual(p.supplier_taxes_id, self.purchase_tax_b)

    def test_ve_product_tax_utility_fields_update_original_taxes(self):
        p = self.env["product.template"].create(self._create_product_vals())
        p.write(
            {
                "l10n_ve_sale_tax_id": self.sale_tax_b.id,
                "l10n_ve_purchase_tax_id": self.purchase_tax_b.id,
            }
        )
        self.assertEqual(p.taxes_id, self.sale_tax_b)
        self.assertEqual(p.supplier_taxes_id, self.purchase_tax_b)

    def test_ve_variant_tax_utility_fields_update_original_taxes(self):
        p = self.env["product.template"].create(self._create_product_vals())
        p.product_variant_id.write(
            {
                "l10n_ve_sale_tax_id": self.sale_tax_b.id,
                "l10n_ve_purchase_tax_id": self.purchase_tax_b.id,
            }
        )
        self.assertEqual(p.taxes_id, self.sale_tax_b)
        self.assertEqual(p.supplier_taxes_id, self.purchase_tax_b)

    def test_ve_product_tax_onchange_rejects_multiple_taxes(self):
        product = self.env["product.template"].new(
            self._create_product_vals(
                taxes_id=[Command.set([self.sale_tax.id, self.sale_tax_b.id])]
            )
        )
        with self.assertRaises(ValidationError):
            product._onchange_l10n_ve_check_exactly_one_tax_per_use()

    def test_ve_product_auto_exent_when_created_without_taxes(self):
        p = self.env["product.template"].create(
            {
                "name": "Producto sin impuestos en vals",
                "company_id": self.env.company.id,
                "list_price": 100.0,
                "standard_price": 50.0,
            }
        )
        self.assertEqual(len(p.taxes_id), 1)
        self.assertEqual(len(p.supplier_taxes_id), 1)
        self.assertEqual(p.taxes_id.amount, 0.0)
        self.assertEqual(p.supplier_taxes_id.amount, 0.0)

    def test_ve_product_allows_zero_list_price(self):
        p = self.env["product.template"].create(
            self._create_product_vals(list_price=0.0, standard_price=0.0)
        )
        self.assertEqual(p.list_price, 0.0)

    def test_ve_product_product_create_allows_zero_list_price(self):
        p = self.env["product.product"].create(
            {
                "name": "Variant zero price VE",
                "type": "service",
                "list_price": 0.0,
                "standard_price": 0.0,
            }
        )
        self.assertEqual(p.list_price, 0.0)

    def test_ve_product_allows_list_price_below_cost(self):
        p = self.env["product.template"].create(
            self._create_product_vals(list_price=40.0, standard_price=50.0)
        )
        self.assertEqual(p.list_price, 40.0)
        self.assertEqual(p.standard_price, 50.0)

    def test_ve_product_allows_list_price_equal_to_cost(self):
        p = self.env["product.template"].create(
            self._create_product_vals(list_price=50.0, standard_price=50.0)
        )
        self.assertEqual(p.list_price, 50.0)

    def test_non_ve_fiscal_company_skips_tax_count_constraint(self):
        us = self.env.ref("base.us")
        company = self.env["res.company"].create(
            {
                "name": "US Co template test",
                "country_id": us.id,
            }
        )
        company.account_fiscal_country_id = us
        p = self.env["product.template"].create(
            {
                "name": "Sin impuestos US",
                "company_id": company.id,
                "list_price": 10.0,
                "taxes_id": [],
                "supplier_taxes_id": [],
            }
        )
        self.assertEqual(len(p.taxes_id), 0)

    def test_non_ve_fiscal_company_skips_price_constraint(self):
        us = self.env.ref("base.us")
        company = self.env["res.company"].create(
            {
                "name": "US Co price test",
                "country_id": us.id,
            }
        )
        company.account_fiscal_country_id = us
        p = self.env["product.template"].create(
            {
                "name": "Precio cero US",
                "company_id": company.id,
                "list_price": 0.0,
                "standard_price": 0.0,
                "taxes_id": [],
                "supplier_taxes_id": [],
            }
        )
        self.assertEqual(p.list_price, 0.0)
