# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class LoyaltyReward(models.Model):
    _inherit = "loyalty.reward"

    def _l10n_ve_company_is_venezuela(self):
        self.ensure_one()
        company = self.company_id or self.program_id.company_id or self.env.company
        country = company.account_fiscal_country_id or company.country_id
        return bool(country and country.code == "VE")

    def _l10n_ve_should_use_global_discount(self):
        """Discount rewards on VE companies use global discounts, not product lines."""
        self.ensure_one()
        return self.reward_type == "discount" and self._l10n_ve_company_is_venezuela()

    def _l10n_ve_get_technical_discount_product_taxes(self, company):
        """Return exempt sale/purchase taxes for loyalty technical products."""
        ProductTemplate = self.env["product.template"]
        if not hasattr(ProductTemplate, "_l10n_ve_get_exent_sale_tax"):
            return self.env["account.tax"], self.env["account.tax"]
        sale_tax = ProductTemplate._l10n_ve_get_exent_sale_tax(company)
        purchase_tax = ProductTemplate._l10n_ve_get_exent_purchase_tax(company)
        return sale_tax, purchase_tax

    def _l10n_ve_prepare_discount_product_values(self, values):
        """Fill technical loyalty product vals for Venezuelan companies."""
        for reward, vals in zip(self, values, strict=False):
            if not reward._l10n_ve_company_is_venezuela():
                continue
            company = (
                reward.company_id or reward.program_id.company_id or self.env.company
            )
            sale_tax, purchase_tax = (
                reward._l10n_ve_get_technical_discount_product_taxes(company)
            )
            if sale_tax:
                vals["taxes_id"] = [(6, 0, sale_tax.ids)]
            if purchase_tax:
                vals["supplier_taxes_id"] = [(6, 0, purchase_tax.ids)]
            vals["list_price"] = 1.0
            vals["lst_price"] = 1.0
        return values

    def _get_discount_product_values(self):
        return self._l10n_ve_prepare_discount_product_values(
            super()._get_discount_product_values()
        )

    def _create_missing_discount_line_products(self):
        ve_rewards = self.filtered(
            lambda reward: not reward.discount_line_product_id
            and reward._l10n_ve_company_is_venezuela()
        )
        if not ve_rewards:
            return super()._create_missing_discount_line_products()
        return super(
            LoyaltyReward,
            self.with_context(
                l10n_ve_skip_product_tax_constraint=True,
                l10n_ve_skip_auto_exent_taxes=True,
            ),
        )._create_missing_discount_line_products()
