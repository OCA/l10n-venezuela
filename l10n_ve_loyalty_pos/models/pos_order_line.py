# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class PosOrderLine(models.Model):
    _inherit = "pos.order.line"

    l10n_ve_global_discount = fields.Boolean(
        string="VE global discount line",
        help="Technical flag: line is a SENIAT global discount, not a product sale.",
    )

    @api.model
    def _load_pos_data_fields(self, config_id):
        fields = super()._load_pos_data_fields(config_id)
        fields.append("l10n_ve_global_discount")
        return fields
