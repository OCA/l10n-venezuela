from odoo import models, fields, api

import logging

_logger = logging.getLogger(__name__)


class ResCurrency(models.Model):
    _inherit = "res.currency"

    def write(self, vals):
        res = super().write(vals)
        pricelist_items = self.env["product.pricelist.item"].search([("currency_to_rate_id", "=", self.id)])
        if pricelist_items:
            pricelist_items.calculate_discount()
        return res


class ResCurrencyRate(models.Model):
    _inherit = "res.currency.rate"

    @api.model_create_multi
    def create(self, list_vals):
        res = super().create(list_vals)
        for record in res:
            pricelist_items = self.env["product.pricelist.item"].search(
                [("currency_to_rate_id", "=", record.currency_id.id)]
            )
            if pricelist_items:
                pricelist_items.calculate_discount()
        return res
