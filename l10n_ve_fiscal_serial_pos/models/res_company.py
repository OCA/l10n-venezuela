# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models


class ResCompany(models.Model):
    _inherit = "res.company"

    @api.model
    def _load_pos_data_fields(self, config_id):
        fields = super()._load_pos_data_fields(config_id)
        for field_name in (
            "l10n_ve_fiscal_flag_21",
            "l10n_ve_fiscal_flag_50",
            "l10n_ve_fiscal_use_barcode",
        ):
            if field_name not in fields:
                fields.append(field_name)
        return fields
