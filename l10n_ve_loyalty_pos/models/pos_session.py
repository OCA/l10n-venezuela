# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class PosSession(models.Model):
    _inherit = "pos.session"

    def _load_pos_data_models(self, config_id):
        models = super()._load_pos_data_models(config_id)
        if "l10n.ve.discount.reason" not in models:
            models.append("l10n.ve.discount.reason")
        return models
