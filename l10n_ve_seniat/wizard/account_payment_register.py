# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class AccountPaymentRegister(models.TransientModel):
    _inherit = "account.payment.register"

    def _l10n_ve_company_is_venezuela(self):
        self.ensure_one()
        country = self.company_id.account_fiscal_country_id
        return bool(country and country.code == "VE")

    def _l10n_ve_installment_lines(self, installments):
        lines = self.env["account.move.line"]
        for installment in installments:
            line = installment.get("line")
            if line:
                lines |= line
        return lines

    def _l10n_ve_is_same_day_company_payment(self, installments):
        self.ensure_one()
        if not self._l10n_ve_company_is_venezuela():
            return False
        if (
            not self.currency_id
            or not self.company_currency_id
            or not self.payment_date
        ):
            return False
        if self.currency_id != self.company_currency_id:
            return False
        if not installments:
            return False
        if any(
            installment.get("type") == "early_payment_discount"
            for installment in installments
        ):
            return False
        lines = self._l10n_ve_installment_lines(installments)
        if not lines:
            return False
        moves = lines.move_id
        if any(not move.is_invoice(include_receipts=True) for move in moves):
            return False
        if any(move.currency_id == move.company_currency_id for move in moves):
            return False
        if any((move.invoice_date or move.date) != self.payment_date for move in moves):
            return False
        open_lines = moves.line_ids.filtered(
            lambda line: line.display_type == "payment_term" and not line.reconciled
        )
        if set(open_lines.ids) != set(lines.ids):
            return False
        return True

    def _l10n_ve_is_same_day_full_unpaid_company_payment(self, installments):
        if not self._l10n_ve_is_same_day_company_payment(installments):
            return False
        lines = self._l10n_ve_installment_lines(installments)
        for line in lines:
            if not line.currency_id.is_zero(
                abs(line.amount_currency) - abs(line.amount_residual_currency)
            ):
                return False
        return True

    def _l10n_ve_same_day_company_amount_from_tax_totals(self, installments):
        self.ensure_one()
        lines = self._l10n_ve_installment_lines(installments)
        total = 0.0
        for move in lines.move_id:
            totals = move.tax_totals or {}
            if "total_amount" in totals:
                total += totals["total_amount"]
            else:
                move_lines = lines.filtered_domain([("move_id", "=", move.id)])
                total += abs(sum(move_lines.mapped("amount_residual")))
        return self.company_currency_id.round(total)

    def _l10n_ve_same_day_company_amount_from_residuals(self, installments):
        self.ensure_one()
        lines = self._l10n_ve_installment_lines(installments)
        return self.company_currency_id.round(abs(sum(lines.mapped("amount_residual"))))

    def _convert_to_wizard_currency(self, installments):
        if self._l10n_ve_is_same_day_full_unpaid_company_payment(installments):
            return self._l10n_ve_same_day_company_amount_from_tax_totals(installments)
        if self._l10n_ve_is_same_day_company_payment(installments):
            return self._l10n_ve_same_day_company_amount_from_residuals(installments)
        return super()._convert_to_wizard_currency(installments)
