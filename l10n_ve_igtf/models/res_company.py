# Copyright 2026 BWEALTHICS LLC
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    l10n_ve_igtf_rate = fields.Float(
        string="Default IGTF Rate (%)",
        default=3.0,
        help="Rate copied to a payment when IGTF is applied.",
    )
    l10n_ve_igtf_expense_account_id = fields.Many2one(
        comodel_name="account.account",
        string="IGTF Expense Account",
        check_company=True,
        domain="[('account_type', 'in', ('expense', 'expense_direct_cost'))]",
    )
    l10n_ve_igtf_perception_account_id = fields.Many2one(
        comodel_name="account.account",
        string="IGTF Perception Account",
        check_company=True,
        domain="[('account_type', 'in', "
        "('liability_current', 'liability_non_current'))]",
    )
    l10n_ve_igtf_perception_agent = fields.Boolean(
        string="IGTF Perception Agent",
        help="Enable this only when SENIAT has designated the company as an "
        "IGTF perception agent.",
    )
    l10n_ve_igtf_perception_agent_date = fields.Date(
        string="IGTF Perception Agent Since",
        help="Date from which the SENIAT designation is effective.",
    )
