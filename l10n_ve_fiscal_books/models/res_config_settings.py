# Copyright 2026 BWEALTHICS LLC
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    pos_l10n_ve_machine_serial = fields.Char(
        related="pos_config_id.l10n_ve_machine_serial",
        readonly=False,
        string="Fiscal Machine Registration Number",
    )
