# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class AccountAccount(models.Model):
    _inherit = "account.account"

    exclude_provision_currency_ids = fields.Many2many(
        "res.currency",
        relation="account_account_exclude_res_currency_provision",
        help="Whether or not we have to make provisions for the selected foreign currencies.",  # noqa: E501
    )
    budget_item_ids = fields.One2many(
        comodel_name="account.report.budget.item.oca", inverse_name="account_id"
    )
