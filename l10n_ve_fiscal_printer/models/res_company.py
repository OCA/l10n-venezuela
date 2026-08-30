# Copyright 2026 BWEALTHICS LLC
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import api, models


class ResCompany(models.Model):
    _inherit = "res.company"

    @api.model
    def _load_pos_data_fields(self, config):
        fields_to_load = super()._load_pos_data_fields(config)
        optional_fields = ("l10n_ve_is_spe", "l10n_ve_igtf_pct")
        return fields_to_load + [
            field_name
            for field_name in optional_fields
            if field_name in self._fields and field_name not in fields_to_load
        ]
