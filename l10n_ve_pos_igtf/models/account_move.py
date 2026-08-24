import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"

    def _l10n_ve_pos_igtf_pos_orders(self):
        self.ensure_one()
        orders = self.sudo().pos_order_ids
        if orders:
            return orders
        return self.env["pos.order"].sudo().search([("account_move", "=", self.id)])

    def _l10n_ve_pos_igtf_pos_payments_for_move(self):
        self.ensure_one()
        orders = self._l10n_ve_pos_igtf_pos_orders()
        if orders:
            pay = orders.payment_ids
            if pay:
                return pay
        return (
            self.env["pos.payment"]
            .sudo()
            .search([("pos_order_id.account_move", "=", self.id)])
        )

    def _l10n_ve_igtf_get_display_tax_group_amounts_from_pos(self):
        self.ensure_one()
        payments = self._l10n_ve_pos_igtf_pos_payments_for_move()
        if not payments:
            return None
        orders = payments.mapped("pos_order_id")
        igtf_sum = sum(orders.mapped("igtf_amount"))
        if self.currency_id.is_zero(igtf_sum):
            igtf_sum = sum(
                payments.mapped(lambda p: p._l10n_ve_pos_get_effective_igtf_amount())
            )
        if self.currency_id.is_zero(igtf_sum):
            _logger.info(
                "l10n_ve_pos_igtf from_pos move_id=%s pos_order_ids=%s "
                "order_igtf_sum=%s payment_igtf_sum=%s",
                self.id,
                len(self.sudo().pos_order_ids),
                sum(orders.mapped("igtf_amount")),
                sum(
                    payments.mapped(
                        lambda p: p._l10n_ve_pos_get_effective_igtf_amount()
                    )
                ),
            )
            return None
        sign = -1.0 if self.move_type == "out_refund" else 1.0
        igtf_mag = abs(self.currency_id.round(igtf_sum))
        bi = sum(orders.mapped("bi_igtf"))
        if not bi:
            bi = sum(
                payments.mapped(
                    lambda p: p._l10n_ve_pos_get_effective_igtf_base_amount()
                )
            )
        b_loc = self.currency_id.round(sign * bi) if bi else 0.0
        b_comp = (
            self.company_currency_id.round(
                self.currency_id._convert(
                    b_loc,
                    self.company_currency_id,
                    self.company_id,
                    self.date,
                )
            )
            if b_loc
            else 0.0
        )
        igtf_cur = self.currency_id.round(-sign * igtf_mag)
        igtf_comp = self.company_currency_id.round(
            self.currency_id._convert(
                -sign * igtf_mag,
                self.company_currency_id,
                self.company_id,
                self.date,
            )
        )
        return b_loc, b_comp, igtf_cur, igtf_comp

    def _l10n_ve_igtf_tax_totals_should_show_igtf_row_extra(self):
        payments = self._l10n_ve_pos_igtf_pos_payments_for_move()
        if not payments:
            return False
        orders = payments.mapped("pos_order_id")
        igtf_sum = sum(orders.mapped("igtf_amount"))
        if self.currency_id.is_zero(igtf_sum):
            igtf_sum = sum(
                payments.mapped(lambda p: p._l10n_ve_pos_get_effective_igtf_amount())
            )
        return not self.currency_id.is_zero(abs(self.currency_id.round(igtf_sum)))

    @api.depends_context("lang")
    @api.depends(
        "invoice_line_ids.currency_rate",
        "invoice_line_ids.tax_base_amount",
        "invoice_line_ids.tax_line_id",
        "invoice_line_ids.price_total",
        "invoice_line_ids.price_subtotal",
        "invoice_payment_term_id",
        "partner_id",
        "currency_id",
        "line_ids.amount_residual",
        "line_ids.amount_residual_currency",
        "line_ids.display_type",
        "line_ids.amount_currency",
        "line_ids.balance",
        "move_type",
        "state",
        "payment_state",
        "country_code",
        "company_id.l10n_ve_igtf_feature_active",
        "company_id.l10n_ve_igtf_allow_invoice_accrual",
        "pos_order_ids.igtf_amount",
        "pos_order_ids.bi_igtf",
        "pos_order_ids.payment_ids.igtf_amount",
        "pos_order_ids.payment_ids.include_igtf",
        "pos_order_ids.payment_ids.amount",
        "pos_order_ids.payment_ids.account_move_id",
        "pos_order_ids.account_move",
    )
    def _compute_tax_totals(self):
        result = super()._compute_tax_totals()
        for move in self:
            merged = move._l10n_ve_igtf_tax_totals_merge_igtf_row()
            if merged is not False:
                move.tax_totals = merged
        return result
