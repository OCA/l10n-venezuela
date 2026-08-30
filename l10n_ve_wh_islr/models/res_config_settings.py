# Copyright 2026 BWEALTHICS LLC
# Part of l10n_ve_wh_islr. License LGPL-3.

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    l10n_ve_islr_wh_account_id = fields.Many2one(
        related="company_id.l10n_ve_islr_wh_account_id", readonly=False
    )
