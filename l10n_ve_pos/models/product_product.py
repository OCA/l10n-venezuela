# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class ProductProduct(models.Model):
    _inherit = "product.product"

    l10n_ve_pos_allow_price_change = fields.Boolean(
        related="product_tmpl_id.l10n_ve_pos_allow_price_change",
        readonly=False,
    )

    @api.model
    def _load_pos_data_fields(self, config_id):
        fields_list = super()._load_pos_data_fields(config_id)
        fields_list.append("l10n_ve_pos_allow_price_change")
        return fields_list
