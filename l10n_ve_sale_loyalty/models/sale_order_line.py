# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        lines._l10n_ve_refresh_order_global_discounts()
        return lines

    def write(self, vals):
        res = super().write(vals)
        if set(vals) & {
            "product_uom_qty",
            "price_unit",
            "discount",
            "tax_id",
            "product_id",
            "display_type",
        }:
            self._l10n_ve_refresh_order_global_discounts()
        return res

    def unlink(self):
        orders = self.order_id
        res = super().unlink()
        orders._l10n_ve_refresh_global_discounts_from_lines()
        return res

    def _l10n_ve_refresh_order_global_discounts(self):
        orders = self.mapped("order_id").filtered(
            lambda order: order.country_code == "VE"
            and order.l10n_ve_global_discount_ids
        )
        if orders:
            orders._l10n_ve_refresh_global_discounts_from_lines()
