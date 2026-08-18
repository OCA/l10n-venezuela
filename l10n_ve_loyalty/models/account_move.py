# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models


class AccountMove(models.Model):
    _inherit = "account.move"

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
        "l10n_ve_global_discount_ids",
        "l10n_ve_global_discount_ids.amount",
        "invoice_line_ids.product_id",
    )
    def _compute_tax_totals(self):
        res = super()._compute_tax_totals()
        AccountTax = self.env["account.tax"]
        for move in self:
            if move.country_code != "VE" or not move.tax_totals:
                continue
            if move.is_invoice(include_receipts=True):
                move.tax_totals = AccountTax._l10n_ve_apply_global_discount_to_tax_totals(
                    move,
                    move.tax_totals,
                )
        return res

    def _l10n_ve_check_credit_note_creation_allowed(self):
        return super()._l10n_ve_check_credit_note_creation_allowed()

    def _l10n_ve_is_post_discount_credit_note(self):
        self.ensure_one()
        return bool(
            self.move_type == "out_refund" and self.l10n_ve_discount_reason_id
        )

    def _l10n_ve_force_refund_to_company_currency(self):
        pending = self._l10n_ve_snapshot_global_discount_amounts_for_currency()
        res = super()._l10n_ve_force_refund_to_company_currency()
        self._l10n_ve_apply_global_discount_amounts_after_currency(pending)
        return res
