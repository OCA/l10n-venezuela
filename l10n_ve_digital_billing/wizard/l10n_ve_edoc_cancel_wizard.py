# Copyright 2026 BWEALTHICS LLC
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import fields, models
from odoo.exceptions import UserError


class L10nVeEdocCancelWizard(models.TransientModel):
    """Cancellation at the digital printing house.

    Exists because cancelling requires a REASON (The Factory HKA asks for it
    as motivoAnulacion) and because cancelling with the provider does not
    cancel the journal entry: the credit note or the accounting cancellation
    is still the accountant's call, this wizard only talks to the provider.
    """

    _name = "l10n.ve.edoc.cancel.wizard"
    _description = "Cancel a document at the digital printing house"

    move_id = fields.Many2one(
        comodel_name="account.move", string="Document", required=True, readonly=True
    )
    reason = fields.Text(string="Cancellation reason", required=True)

    def action_confirm(self):
        self.ensure_one()
        move = self.move_id
        if move.l10n_ve_edoc_state not in ("sent", "assigned"):
            raise UserError(
                self.env._(
                    "%(document)s was not issued at the digital printing house.",
                    document=move.display_name,
                )
            )
        # _l10n_ve_edoc_do_cancel never raises: if it did, the rollback
        # would take the log entry with it. The failure is shown as a
        # notification and the detail stays on the document and in the log.
        if move._l10n_ve_edoc_do_cancel(self.reason):
            return {"type": "ir.actions.act_window_close"}
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "type": "danger",
                "title": self.env._(
                    "The printing house did not accept the cancellation"
                ),
                "message": move.l10n_ve_edoc_error
                or self.env._("Check the digital printing house log."),
                "sticky": True,
            },
        }
