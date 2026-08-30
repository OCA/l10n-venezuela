# Copyright 2011-2016 Vauxoo
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import _, fields, models
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = "account.move"

    wh_iva_id = fields.Many2one(
        comodel_name="account.wh.iva",
        string="VAT Withholding Voucher",
        copy=False,
        readonly=True,
    )

    def action_generate_wh_iva(self):
        self.ensure_one()
        if self.wh_iva_id:
            raise UserError(_("VAT Withholding Voucher already exists for this move."))
        if self.move_type not in [
            "out_invoice",
            "in_invoice",
            "out_refund",
            "in_refund",
        ]:
            raise UserError(
                _("Only invoices and refunds can generate VAT Withholdings.")
            )

        voucher = self.env["account.wh.iva"].create(
            {
                "partner_id": self.partner_id.id,
                "type": self.move_type,
                "date": self.invoice_date or fields.Date.today(),
                "line_ids": [(0, 0, {"move_id": self.id})],
            }
        )
        # Trigger onchange
        for line in voucher.line_ids:
            line._onchange_move_id()
        self.wh_iva_id = voucher.id
        return {
            "name": _("VAT Withholding Voucher"),
            "type": "ir.actions.act_window",
            "res_model": "account.wh.iva",
            "res_id": voucher.id,
            "view_mode": "form",
            "target": "current",
        }
