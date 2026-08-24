from odoo import api, models


class ProductPricelist(models.Model):
    _inherit = 'product.pricelist'

    @api.model
    def _load_pos_data_fields(self, config_id):
        fields = super()._load_pos_data_fields(config_id)
        fields.append('currency_id')
        return fields
