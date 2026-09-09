# Copyright 2026 BWEALTHICS LLC
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import fields, models


class PosSession(models.Model):
    _inherit = "pos.session"

    l10n_ve_z_number = fields.Char(
        string="Fiscal Z Report Number",
        copy=False,
        tracking=True,
        help="Number returned by the fiscal machine for this session's Z report.",
    )
