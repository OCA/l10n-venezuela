from odoo import api, models


class ResCurrency(models.Model):
    _inherit = "res.currency"

    @api.model
    def _load_pos_data_domain(self, data):
        # Load all active currencies so pricelists / payments in USD, VES, etc. resolve.
        return [("active", "=", True)]

    @api.model
    def _load_pos_data_fields(self, config_id):
        fields_list = super()._load_pos_data_fields(config_id)
        if "inverse_rate" not in fields_list:
            fields_list.append("inverse_rate")
        return fields_list
