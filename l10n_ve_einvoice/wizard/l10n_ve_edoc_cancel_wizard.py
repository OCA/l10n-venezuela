# Copyright 2026 BWEALTHICS LLC
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import fields, models
from odoo.exceptions import UserError


class L10nVeEdocCancelWizard(models.TransientModel):
    _name = "l10n.ve.edoc.cancel.wizard"
    _description = "Cancel Venezuelan Electronic Document"

    move_id = fields.Many2one(
        comodel_name="account.move",
        string="Document",
        required=True,
        readonly=True,
    )
    reason = fields.Text(string="Cancellation Reason", required=True)

    def action_confirm(self):
        self.ensure_one()
        move = self.move_id
        if move.l10n_ve_edoc_state not in ("sent", "assigned"):
            raise UserError(
                self.env._(
                    "%(document)s has not been issued by its provider.",
                    document=move.display_name,
                )
            )
        if move._l10n_ve_edoc_do_cancel(self.reason):
            return {"type": "ir.actions.act_window_close"}
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "type": "danger",
                "title": self.env._("The provider rejected the cancellation"),
                "message": move.l10n_ve_edoc_error
                or self.env._("Review the electronic document log."),
                "sticky": True,
            },
        }
