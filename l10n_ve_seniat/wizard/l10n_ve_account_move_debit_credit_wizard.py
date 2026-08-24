# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, fields, models
from odoo.exceptions import UserError


class L10nVeAccountMoveDebitCreditWizard(models.TransientModel):
    _name = "l10n_ve.account.move.debit.credit.wizard"
    _description = "Nota de crédito por nota de débito adicional (Venezuela)"

    move_id = fields.Many2one(
        "account.move",
        string="Factura",
        required=True,
        ondelete="cascade",
    )
    debit_note_ids = fields.Many2many(
        "account.move",
        string="Notas de débito",
        required=True,
    )
    reason = fields.Char(
        string="Motivo",
        required=True,
    )

    def action_create_credit_note(self):
        """Genera NC por reversión de notas de débito adicionales.

        Notes
        -----
        Art. 22-24 PA SNAT/2011/0071: NC referenciada a factura y ND afectada.
        """

        self.ensure_one()
        invoice = self.move_id
        if (
            invoice.country_code != "VE"
            or not invoice._l10n_ve_is_invoice_for_credit_debit()
        ):
            raise UserError(
                _("Esta acción solo aplica a facturas de cliente o proveedor (VE).")
            )
        unreversed = invoice._l10n_ve_get_unreversed_debit_notes()
        invalid = self.debit_note_ids - unreversed
        if invalid:
            raise UserError(
                _(
                    "Las notas de débito %(debits)s ya fueron revertidas o no "
                    "pertenecen a la factura.",
                    debits=", ".join(invalid.mapped("display_name")),
                )
            )
        if not self.debit_note_ids:
            raise UserError(_("Debe seleccionar al menos una nota de débito."))
        line_vals = invoice._l10n_ve_prepare_credit_note_lines_from_debit_notes(
            self.debit_note_ids
        )
        if not line_vals:
            raise UserError(
                _("Las notas de débito seleccionadas no tienen líneas para revertir.")
            )
        debit_names = ", ".join(self.debit_note_ids.mapped("name"))
        credit_note = (
            self.env["account.move"]
            .with_context(l10n_ve_credit_note_for_debit_note=True)
            .create(
                {
                    "move_type": invoice._l10n_ve_refund_move_type(),
                    "reversed_entry_id": invoice.id,
                    "partner_id": invoice.partner_id.id,
                    "journal_id": invoice.journal_id.id,
                    "invoice_date": fields.Date.context_today(self),
                    "ref": _(
                        "Reversión nota(s) de débito %(debits)s de factura "
                        "%(invoice)s: %(reason)s",
                        debits=debit_names,
                        invoice=invoice.name,
                        reason=self.reason,
                    ),
                    "l10n_ve_debit_note_reversed_ids": [
                        (6, 0, self.debit_note_ids.ids)
                    ],
                    "invoice_line_ids": line_vals,
                }
            )
        )
        return {
            "type": "ir.actions.act_window",
            "name": _("Nota de crédito"),
            "res_model": "account.move",
            "view_mode": "form",
            "res_id": credit_note.id,
        }
