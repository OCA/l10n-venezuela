# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, models


class AccountMoveReversal(models.TransientModel):
    _inherit = "account.move.reversal"

    def reverse_moves(self, is_modify=False):
        action = super().reverse_moves(is_modify=is_modify)
        for wizard in self:
            for move in wizard.new_move_ids.filtered(
                lambda record: record.country_code == "VE"
            ):
                origin = move.reversed_entry_id.display_name or ""
                if move.move_type == "out_refund":
                    move._l10n_ve_audit_log_fiscal_event(
                        "draft_credit_note",
                        _(
                            "Creación de nota de crédito borrador %(document)s "
                            "de la factura %(origin)s"
                        )
                        % {"document": move.display_name, "origin": origin},
                    )
                elif move.debit_origin_id:
                    move._l10n_ve_audit_log_fiscal_event(
                        "draft_debit_note",
                        _(
                            "Creación de nota de débito borrador %(document)s "
                            "de la factura %(origin)s"
                        )
                        % {"document": move.display_name, "origin": origin},
                    )
        return action
