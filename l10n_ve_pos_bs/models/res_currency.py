# Copyright 2026 BWEALTHICS LLC
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, models
from odoo.fields import Domain


class ResCurrency(models.Model):
    _inherit = "res.currency"

    @api.model
    def _load_pos_data_domain(self, data, config):
        return Domain.OR(
            [
                super()._load_pos_data_domain(data, config),
                [("id", "=", self.env.ref("base.VES").id)],
            ]
        )
