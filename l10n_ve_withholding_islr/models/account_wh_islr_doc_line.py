# Copyright 2011-2016 Vauxoo
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import api, fields, models


class AccountWhIslrDocLine(models.Model):
    _name = "account.wh.islr.doc.line"
    _description = "ISLR Withholding Document Line"

    islr_doc_id = fields.Many2one(
        comodel_name="account.wh.islr.doc",
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
    concept_id = fields.Many2one(
        comodel_name="islr.wh.concept",
        string="ISLR Concept",
        required=True,
    )
    base_amount = fields.Monetary(
        string="Base Amount",
        currency_field="currency_id",
        required=True,
    )
    wh_percentage = fields.Float(
        string="Retention Rate (%)",
        default=2.0,
    )
    subtract_amount = fields.Monetary(
        string="Subtraction Amount",
        currency_field="currency_id",
        default=0.0,
    )
    amount_ret = fields.Monetary(
        string="Withheld ISLR",
        compute="_compute_amount_ret",
        store=True,
        currency_field="currency_id",
    )
    currency_id = fields.Many2one(
        related="islr_doc_id.currency_id",
        store=True,
    )

    @api.depends("base_amount", "wh_percentage", "subtract_amount")
    def _compute_amount_ret(self):
        for line in self:
            calc = (
                line.base_amount * (line.wh_percentage / 100.0)
            ) - line.subtract_amount
            line.amount_ret = max(calc, 0.0)

    @api.onchange("move_id", "concept_id")
    def _onchange_concept_or_move(self):
        if self.move_id:
            self.base_amount = self.move_id.amount_untaxed
            if self.concept_id and self.islr_doc_id.partner_id:
                pt = self.islr_doc_id.partner_id.person_type or "pjdo"
                rate_rec = self.concept_id.withholding_rate_ids.filtered(
                    lambda r: r.person_type == pt
                )
                if rate_rec:
                    rate = rate_rec[0]
                    self.wh_percentage = rate.wh_percentage
                    if rate.subtract_ut > 0:
                        ut_val = self.env["l10n.ut"].get_amount_ut(
                            self.islr_doc_id.date
                        )
                        sub_ut = rate.subtract_ut * ut_val
                        self.subtract_amount = sub_ut * (rate.wh_percentage / 100.0)
                    else:
                        self.subtract_amount = 0.0
