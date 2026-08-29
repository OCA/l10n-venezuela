# Copyright 2026 BWEALTHICS LLC
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class L10nVeMunicipality(models.Model):
    _name = "l10n.ve.municipality"
    _description = "Venezuelan Municipality"
    _order = "state_id, name"

    name = fields.Char(required=True)
    state_id = fields.Many2one(
        comodel_name="res.country.state",
        string="State",
        required=True,
        ondelete="restrict",
        domain=[("country_id.code", "=", "VE")],
    )
    code = fields.Char()
    active = fields.Boolean(default=True)

    _name_state_uniq = models.Constraint(
        "UNIQUE(name, state_id)",
        "A municipality with this name already exists in the state.",
    )
