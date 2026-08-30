# Copyright 2011-2016 Vauxoo
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import _, fields, models
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = "account.move"

    wh_islr_doc_id = fields.Many2one(
        comodel_name="account.wh.islr.doc",
        string="ISLR Withholding Voucher",
        copy=False,
        readonly=True,
    )
    islr_concept_id = fields.Many2one(
        comodel_name="islr.wh.concept",
        string="Default ISLR Concept",
    )

    def action_generate_wh_islr(self):
        self.ensure_one()
        if self.wh_islr_doc_id:
            raise UserError(_("ISLR Withholding Voucher already exists for this move."))
        if self.move_type not in [
            "out_invoice",
            "in_invoice",
            "out_refund",
            "in_refund",
        ]:
            raise UserError(
                _("Only invoices and refunds can generate ISLR Withholdings.")
            )

        default_concept = self.islr_concept_id or self.env["islr.wh.concept"].search(
            [], limit=1
        )
        voucher = self.env["account.wh.islr.doc"].create(
            {
                "partner_id": self.partner_id.id,
                "type": self.move_type,
                "date": self.invoice_date or fields.Date.today(),
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "move_id": self.id,
                            "concept_id": (
                                default_concept.id if default_concept else False
                            ),
                            "base_amount": self.amount_untaxed,
                        },
                    )
                ],
            }
        )
        for line in voucher.line_ids:
            line._onchange_concept_or_move()
        self.wh_islr_doc_id = voucher.id
        return {
            "name": _("ISLR Withholding Voucher"),
            "type": "ir.actions.act_window",
            "res_model": "account.wh.islr.doc",
            "res_id": voucher.id,
            "view_mode": "form",
            "target": "current",
        }
