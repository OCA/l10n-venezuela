# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models
from odoo.tools import float_is_zero


class AccountMove(models.Model):
    _inherit = "account.move"

    def _l10n_ve_pos_ewallet_spend_amount_company(self):
        self.ensure_one()
        if "pos_order_ids" not in self._fields:
            return 0.0
        total = 0.0
        for order in self.pos_order_ids:
            amount = order._l10n_ve_pos_ewallet_spend_amount(with_tax=False)
            if float_is_zero(amount, precision_rounding=order.currency_id.rounding):
                continue
            conv_date = (
                order.date_order.date()
                if order.date_order
                else (self.invoice_date or self.date)
            )
            total += order.currency_id._convert(
                amount,
                self.company_currency_id,
                self.company_id,
                conv_date,
            )
        return self.company_currency_id.round(total)

    def _l10n_ve_fiscal_serial_global_discount_amount(self):
        amount = super()._l10n_ve_fiscal_serial_global_discount_amount()
        ewallet_amount = self._l10n_ve_pos_ewallet_spend_amount_company()
        if float_is_zero(ewallet_amount, precision_rounding=self.company_currency_id.rounding):
            return amount
        return self.company_currency_id.round(max(amount - ewallet_amount, 0.0))

    def _l10n_ve_fiscal_serial_payment_lines_from_pos_orders(self):
        lines = super()._l10n_ve_fiscal_serial_payment_lines_from_pos_orders()
        ewallet_amount = self._l10n_ve_pos_ewallet_spend_amount_company()
        if float_is_zero(ewallet_amount, precision_rounding=self.company_currency_id.rounding):
            return lines
        label_order = self.pos_order_ids[:1]
        payment_method = (
            label_order._l10n_ve_ewallet_fiscal_payment_code()
            if label_order
            else "24"
        )
        lines.append(
            {
                "amount": ewallet_amount,
                "payment_method": payment_method,
            }
        )
        return lines
