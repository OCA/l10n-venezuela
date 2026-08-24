# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models


class ResCompany(models.Model):
    _inherit = "res.company"

    def write(self, vals):
        res = super().write(vals)
        if any(
            k in vals for k in ("sale_discount_product_id", "account_fiscal_country_id")
        ):
            for company in self:
                company._l10n_ve_patch_sale_discount_product()
        return res

    def _l10n_ve_patch_sale_discount_product(self):
        self.ensure_one()
        if self.account_fiscal_country_id.code != "VE":
            return
        product = self.sale_discount_product_id
        if not product:
            return
        tmpl = product.product_tmpl_id
        vals = {}
        if not tmpl.taxes_id and self.account_sale_tax_id:
            vals["taxes_id"] = [(6, 0, [self.account_sale_tax_id.id])]
        if not tmpl.supplier_taxes_id and self.account_purchase_tax_id:
            vals["supplier_taxes_id"] = [(6, 0, [self.account_purchase_tax_id.id])]
        if vals:
            tmpl.write(vals)

    @api.model
    def _l10n_ve_seniat_sale_fix_discount_products(self):
        ve = self.env.ref("base.ve", raise_if_not_found=False)
        if not ve:
            return
        companies = self.search([("account_fiscal_country_id", "=", ve.id)])
        for company in companies:
            company._l10n_ve_patch_sale_discount_product()
