# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class L10nVeDiscountReason(models.Model):
    _name = "l10n.ve.discount.reason"
    _description = "Venezuela global discount reason"
    _order = "sequence, id"

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    @api.model
    def _l10n_ve_get_default(self):
        return self.search([("active", "=", True)], order="sequence, id", limit=1)
