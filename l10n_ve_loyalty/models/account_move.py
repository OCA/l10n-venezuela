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

    def l10n_ve_report_invoice_lines(self):
        self.ensure_one()
        lines = self.invoice_line_ids.sorted(key=lambda line: (line.sequence, line.id))
        if self.company_id.account_fiscal_country_id.code != "VE":
            return lines
        disc = getattr(self.company_id, "sale_discount_product_id", False)
        if not disc:
            return lines

        def _is_discount_product_line(line):
            return line.display_type == "product" and line.product_id == disc

        discount_lines = lines.filtered(_is_discount_product_line)
        if not discount_lines:
            return lines
        return lines.filtered(lambda line: not _is_discount_product_line(line)) + (
            discount_lines
        )

    def _l10n_ve_check_credit_note_creation_allowed(self):
        """Hook extended by l10n_ve_seniat with fiscal credit-note rules."""

    def _l10n_ve_force_refund_to_company_currency(self):
        """Hook extended by l10n_ve_seniat for dual-currency refunds."""
