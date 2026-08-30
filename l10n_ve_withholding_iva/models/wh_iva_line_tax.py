# Copyright 2011-2016 Vauxoo
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import api, fields, models


class AccountWhIvaLineTax(models.Model):
    _name = "account.wh.iva.line.tax"
    _description = "VAT Withholding Tax Line Breakdown"

    wh_iva_line_id = fields.Many2one(
        comodel_name="account.wh.iva.line",
        string="Voucher Line",
        ondelete="cascade",
        required=True,
    )
    tax_id = fields.Many2one(
        comodel_name="account.tax",
        string="Tax",
        required=True,
    )
    base_amount = fields.Float(string="Base Amount")
    tax_amount = fields.Float(string="Tax Amount")
    wh_rate = fields.Float(string="Retention Rate (%)", default=75.0)
    amount_ret = fields.Float(
        string="Withheld Amount",
        compute="_compute_ret",
        store=True,
    )

    @api.depends("tax_amount", "wh_rate")
    def _compute_ret(self):
        for rec in self:
            rec.amount_ret = rec.tax_amount * (rec.wh_rate / 100.0)
