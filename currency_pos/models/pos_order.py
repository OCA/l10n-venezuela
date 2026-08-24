from odoo import models
from odoo.tools import float_is_zero


class PosOrder(models.Model):
    _inherit = "pos.order"

    def _oca_absorb_foreign_payment_rounding(self):
        for order in self:
            if not order.config_id.allow_multi_currency_payment:
                continue
            foreign_payments = order.payment_ids.filtered(
                lambda payment: not payment.is_change
                and payment.is_foreign_currency_payment
            )
            if not foreign_payments:
                continue
            currency = order.currency_id
            diff = currency.round(order.amount_total - order.amount_paid)
            if float_is_zero(diff, precision_rounding=currency.rounding):
                continue
            if abs(diff) > currency.rounding + 1e-9:
                continue
            payment = foreign_payments[-1]
            payment.write({"amount": currency.round(payment.amount + diff)})
            order.write({"amount_paid": sum(order.payment_ids.mapped("amount"))})

    def _process_payment_lines(self, pos_order, order, pos_session, draft):
        res = super()._process_payment_lines(pos_order, order, pos_session, draft)
        if not draft:
            order._oca_absorb_foreign_payment_rounding()
        return res

    def _process_order(self, order, existing_order):
        order_id = super()._process_order(order, existing_order)
        self.browse(order_id).payment_ids._oca_fill_multicurrency_values()
        return order_id
