from odoo import models, fields, api

import logging

_logger = logging.getLogger(__name__)


class ProductPricelistItem(models.Model):
    _inherit = "product.pricelist.item"

    currency_to_rate_id = fields.Many2one("res.currency")

    def write(self, vals):
        res = super().write(vals)
        if "currency_to_rate_id" in vals:
            self.calculate_discount()
        return res

    def calculate_discount(self):
        for item in self:
            if item.currency_to_rate_id:
                to_currency = item.currency_to_rate_id
                from_currency = item.pricelist_id.currency_id
                percentaje = (
                    (from_currency.inverse_rate - to_currency.inverse_rate) / from_currency.inverse_rate
                ) * 100
                item.price_discount = percentaje
