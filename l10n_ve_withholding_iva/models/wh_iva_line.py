# Copyright 2011-2016 Vauxoo
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import api, fields, models


class AccountWhIvaLine(models.Model):
    _name = "account.wh.iva.line"
    _description = "VAT Withholding Voucher Line"

    wh_iva_id = fields.Many2one(
        comodel_name="account.wh.iva",
        string="Voucher",
        ondelete="cascade",
        required=True,
    )
    move_id = fields.Many2one(
        comodel_name="account.move",
        string="Invoice",
        required=True,
        domain=(
            "[('partner_id', '=', parent.partner_id), "
            "('move_type', 'in', "
            "('out_invoice', 'in_invoice', 'out_refund', 'in_refund'))]"
        ),
    )
    tax_line_ids = fields.One2many(
        comodel_name="account.wh.iva.line.tax",
        inverse_name="wh_iva_line_id",
        string="Taxes Breakdown",
        copy=True,
    )
    base_amount = fields.Monetary(
        string="Base Amount",
        compute="_compute_line_totals",
        store=True,
        currency_field="currency_id",
    )
    tax_amount = fields.Monetary(
        string="Tax Amount",
        compute="_compute_line_totals",
        store=True,
        currency_field="currency_id",
    )
    amount_ret = fields.Monetary(
        string="Withheld Amount",
        compute="_compute_line_totals",
        store=True,
        currency_field="currency_id",
    )
    wh_rate = fields.Float(
        string="Retention Rate (%)",
        default=75.0,
    )
    currency_id = fields.Many2one(
        related="wh_iva_id.currency_id",
        store=True,
    )

    @api.depends(
        "tax_line_ids.base_amount",
        "tax_line_ids.tax_amount",
        "tax_line_ids.amount_ret",
    )
    def _compute_line_totals(self):
        for line in self:
            line.base_amount = sum(line.tax_line_ids.mapped("base_amount"))
            line.tax_amount = sum(line.tax_line_ids.mapped("tax_amount"))
            line.amount_ret = sum(line.tax_line_ids.mapped("amount_ret"))

    @api.onchange("move_id")
    def _onchange_move_id(self):
        if self.move_id:
            lines = []
            rate = self.wh_iva_id.partner_id.wh_iva_rate or 75.0
            self.wh_rate = rate
            for tax_line in self.move_id.line_ids.filtered(
                lambda t_line: t_line.tax_line_id
            ):
                tax = tax_line.tax_line_id
                base = tax_line.tax_base_amount or abs(tax_line.balance)
                tax_amt = abs(tax_line.balance)
                ret_amt = tax_amt * (rate / 100.0)
                lines.append(
                    (
                        0,
                        0,
                        {
                            "tax_id": tax.id,
                            "base_amount": base,
                            "tax_amount": tax_amt,
                            "wh_rate": rate,
                            "amount_ret": ret_amt,
                        },
                    )
                )
            self.tax_line_ids = lines
