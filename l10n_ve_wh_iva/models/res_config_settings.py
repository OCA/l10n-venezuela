# Copyright 2026 BWEALTHICS LLC
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    l10n_ve_is_spe = fields.Boolean(
        related="company_id.l10n_ve_is_spe",
        readonly=False,
    )
    l10n_ve_spe_date = fields.Date(
        related="company_id.l10n_ve_spe_date",
        readonly=False,
    )
    l10n_ve_iva_wh_agent_account_id = fields.Many2one(
        related="company_id.l10n_ve_iva_wh_agent_account_id",
        readonly=False,
    )
    l10n_ve_iva_wh_received_account_id = fields.Many2one(
        related="company_id.l10n_ve_iva_wh_received_account_id",
        readonly=False,
    )
