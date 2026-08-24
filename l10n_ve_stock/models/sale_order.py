# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def _action_confirm(self):
        res = super()._action_confirm()
        self.filtered(
            lambda o: o.country_code == "VE"
        )._l10n_ve_split_delivery_pickings()
        return res

    def _l10n_ve_split_delivery_pickings(self):
        for order in self:
            journal = order.journal_id
            if not journal:
                continue
            if journal.l10n_ve_emission_medium == "fiscal_machine":
                continue
            section = journal.l10n_ve_invoice_section_id
            book = section.book_id if section else False
            if book:
                max_moves = max(book.l10n_ve_max_picking_lines or 10, 1)
            elif journal.l10n_ve_emission_medium not in ("free", "fiscal_machine"):
                max_moves = journal._l10n_ve_journal_picking_line_limit()
                if not max_moves:
                    continue
            else:
                continue
            pickings = order.picking_ids.filtered(
                lambda p: p.state not in ("done", "cancel")
                and p.picking_type_id.code == "outgoing"
            )
            for picking in pickings:
                moves = picking.move_ids.filtered(
                    lambda m: m.state not in ("done", "cancel")
                ).sorted(key=lambda m: (m.sequence, m.id))
                if len(moves) <= max_moves:
                    continue
                chunks = [
                    moves[i : i + max_moves] for i in range(0, len(moves), max_moves)
                ]
                for chunk in chunks[1:]:
                    new_picking = picking.copy(
                        default={
                            "name": "/",
                            "move_ids": [],
                            "move_line_ids": [],
                        }
                    )
                    chunk.write({"picking_id": new_picking.id})
                    if new_picking.state == "draft":
                        new_picking.action_confirm()
