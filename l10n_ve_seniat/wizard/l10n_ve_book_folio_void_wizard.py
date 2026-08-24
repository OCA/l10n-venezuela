# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, fields, models
from odoo.exceptions import UserError


class L10nVeBookFolioVoidWizard(models.TransientModel):
    _name = "l10n_ve.book.folio.void.wizard"
    _description = "Anular folio en talonario (saltar correlativo)"

    book_id = fields.Many2one(
        "account.book",
        string="Talonario",
        required=True,
    )
    section_id = fields.Many2one(
        "account.book.section",
        string="Tramo",
        required=True,
        domain="[('book_id', '=', book_id)]",
    )
    reason = fields.Text(
        string="Motivo",
        required=True,
        help=(
            "Motivo por el cual se consume un número de control sin "
            "documento asociado."
        ),
    )

    def action_confirm(self):
        """Confirma anulación de folio en talonario fiscal.

        Notes
        -----
        Art. 27 PA SNAT/2011/0071: control de numeración.
        Art. 28 PA SNAT/2011/0071: integridad documental.
        """

        self.ensure_one()
        if not (self.reason or "").strip():
            raise UserError(_("Debe indicar el motivo de la anulación del folio."))
        self.book_id.l10n_ve_allocate_void_folio(self.section_id, self.reason.strip())
        return {"type": "ir.actions.act_window_close"}
