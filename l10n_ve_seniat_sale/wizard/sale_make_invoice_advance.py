# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, models
from odoo.exceptions import UserError


class SaleAdvancePaymentInv(models.TransientModel):
    _inherit = "sale.advance.payment.inv"

    def create_invoices(self):
        ve_orders = self.sale_order_ids.filtered(
            lambda order: order.country_code == "VE"
        )
        if not ve_orders:
            return super().create_invoices()
        if ve_orders != self.sale_order_ids:
            raise UserError(
                _(
                    "No se puede mezclar pedidos venezolanos y de otros países "
                    "en el mismo asistente de facturación."
                )
            )
        if self.advance_payment_method in ("percentage", "fixed"):
            raise UserError(
                _("En la localización venezolana no se permiten facturas de anticipo.")
            )
        invoices = ve_orders._create_invoices(
            final=self.deduct_down_payments,
            grouped=not self.consolidated_billing,
        )
        return ve_orders.action_view_invoice(invoices=invoices)
