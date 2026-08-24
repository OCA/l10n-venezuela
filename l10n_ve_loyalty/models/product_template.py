# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    def _l10n_ve_is_sale_discount_template(self):
        self.ensure_one()
        Company = self.env["res.company"]
        if "sale_discount_product_id" not in Company._fields:
            return False
        ve = self.env.ref("base.ve", raise_if_not_found=False)
        if not ve:
            return False
        discount_products = Company.search(
            [("account_fiscal_country_id", "=", ve.id)]
        ).mapped("sale_discount_product_id")
        if not discount_products:
            return False
        return bool(self.product_variant_ids & discount_products)

    def _l10n_ve_is_loyalty_reward_discount_template(self):
        self.ensure_one()
        if "loyalty.reward" not in self.env:
            return False
        products = self.product_variant_ids
        if not products:
            return False
        return bool(
            self.env["loyalty.reward"]
            .sudo()
            .search_count(
                [("discount_line_product_id", "in", products.ids)],
                limit=1,
            )
        )
