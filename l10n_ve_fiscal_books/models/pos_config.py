# Copyright 2026 BWEALTHICS LLC
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import fields, models


class PosConfig(models.Model):
    _inherit = "pos.config"

    l10n_ve_machine_serial = fields.Char(
        string="Fiscal Machine Registration Number",
        help="Registration number of the fiscal machine associated with this point "
        "of sale. It is included in the daily sales-book row.",
    )
