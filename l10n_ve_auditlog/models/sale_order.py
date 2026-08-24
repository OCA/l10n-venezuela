# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def _create_invoices(self, grouped=False, final=False, date=None):
        moves = super()._create_invoices(grouped=grouped, final=final, date=date)
        for order in self.filtered(lambda record: record.country_code == "VE"):
            order_name = order.name
            order_moves = moves.filtered(
                lambda move, origin=order_name: move.invoice_origin == origin
                and move.state == "draft"
            )
            for move in order_moves:
                move._l10n_ve_audit_log_fiscal_event(
                    "draft_invoice_from_order",
                    _(
                        "Creación de factura borrador %(document)s "
                        "del pedido %(order)s"
                    )
                    % {"document": move.display_name, "order": order.name},
                )
        return moves
