import logging

from odoo import fields, models
from odoo.tools.translate import _

_logger = logging.getLogger(__name__)


class AccountMoveReversal(models.TransientModel):
    """
    Account move reversal wizard, it cancel an account move by reversing it.
    """

    _inherit = "account.move.reversal"

    def _prepare_default_reversal(self, move):
        return {
            "ref": _(
                "Reversión de: %(move_name)s %(reason)s",
                move_name=move.name,
                reason=self.reason,
            )
            if self.reason
            else _("Reversión de: %s") % (move.name),
            "date": self.date or move.date,
            "invoice_date": move.is_invoice(include_receipts=True)
            and (self.date or move.date)
            or False,
            "journal_id": self.journal_id and self.journal_id.id or move.journal_id.id,
            "invoice_payment_term_id": None,
            "auto_post": True if self.date > fields.Date.context_today(self) else False,
            "invoice_user_id": move.invoice_user_id.id,
            "l10n_ve_document_number": "",
        }

    # TODO: ver si esto es necesario.
    # def reverse_moves(self):
    #     """ Forzamos el definir limpio"""
    #     res = super(AccountMoveReversal, self).reverse_moves()
    #     # Nunca esta pasando por aquí.
    #     for rec in self:
    #         self.move_ids.l10n_ve_document_number = ""
    #     return res
