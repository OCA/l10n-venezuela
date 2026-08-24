# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models


class LoyaltyProgram(models.Model):
    _inherit = "loyalty.program"

    @api.model
    def _load_pos_data_fields(self, config_id):
        fields_list = super()._load_pos_data_fields(config_id)
        if "currency_id" not in fields_list:
            fields_list.append("currency_id")
        return fields_list
