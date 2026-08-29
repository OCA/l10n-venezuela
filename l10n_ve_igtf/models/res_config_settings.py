# Copyright 2026 BWEALTHICS LLC
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    l10n_ve_igtf_rate = fields.Float(
        related="company_id.l10n_ve_igtf_rate",
        readonly=False,
    )
    l10n_ve_igtf_expense_account_id = fields.Many2one(
        related="company_id.l10n_ve_igtf_expense_account_id",
        readonly=False,
        check_company=True,
    )
    l10n_ve_igtf_perception_account_id = fields.Many2one(
        related="company_id.l10n_ve_igtf_perception_account_id",
        readonly=False,
        check_company=True,
    )
    l10n_ve_igtf_perception_agent = fields.Boolean(
        related="company_id.l10n_ve_igtf_perception_agent",
        readonly=False,
    )
    l10n_ve_igtf_perception_agent_date = fields.Date(
        related="company_id.l10n_ve_igtf_perception_agent_date",
        readonly=False,
    )
