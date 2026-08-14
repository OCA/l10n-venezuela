# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models


class L10nVeDiscountReason(models.Model):
    _name = "l10n.ve.discount.reason"
    _inherit = ["l10n.ve.discount.reason", "pos.load.mixin"]

    @api.model
    def _load_pos_data_domain(self, data):
        return [("active", "=", True)]

    @api.model
    def _load_pos_data_fields(self, config_id):
        return ["id", "name", "sequence", "active"]
