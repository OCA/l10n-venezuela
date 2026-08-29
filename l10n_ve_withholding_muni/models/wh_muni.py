# Copyright 2011-2016 Vauxoo
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import fields, models


class AccountWhMuni(models.Model):
    _name = "account.wh.muni"
    _description = "Municipal Withholding Voucher"
    _order = "date desc, name desc"

    name = fields.Char(string="Voucher Number", required=True, copy=False, default="/")
    partner_id = fields.Many2one(comodel_name="res.partner", string="Partner", required=True)
    date = fields.Date(string="Date", required=True, default=fields.Date.context_today)
    state = fields.Selection([("draft", "Draft"), ("done", "Posted"), ("cancel", "Cancelled")], string="State", default="draft")
    amount_total_ret = fields.Float(string="Total Withheld Amount", default=0.0)
