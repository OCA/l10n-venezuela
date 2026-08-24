# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, fields, models
from odoo.exceptions import AccessError, UserError


class L10nVeAccountMoveCancelWizard(models.TransientModel):
    _name = "l10n_ve.account.move.cancel.wizard"
    _description = "Anular documento con motivo (Venezuela)"

    move_id = fields.Many2one(
        "account.move",
        required=True,
        ondelete="cascade",
    )
    reason_id = fields.Many2one(
        "l10n_ve.invoice.cancel.reason",
        string="Motivo de anulación",
        required=True,
    )

    def action_confirm(self):
        """Anula el documento registrando motivo de anulación.

        Notes
        -----
        Art. 18 PA SNAT/2024/000102: trazabilidad de anulaciones.
        Art. 11 PA SNAT/2011/0071: no aplica a máquina fiscal.
        """

        self.ensure_one()
        if not self.env.user.has_group("l10n_ve_seniat.group_l10n_ve_invoice_void"):
            raise AccessError(_("No tiene permiso para anular facturas de cliente."))
        move = self.move_id
        ve_code = self.env.ref("base.ve").code
        if move.country_code != ve_code:
            raise UserError(_("Este asistente solo aplica a documentos de Venezuela."))
        if not move._l10n_ve_allows_cancel_wizard():
            raise UserError(
                _("No se puede anular documentos emitidos en máquina fiscal.")
            )
        move.write({"l10n_ve_cancel_reason_id": self.reason_id.id})
        move.button_cancel()
        return {"type": "ir.actions.act_window_close"}
