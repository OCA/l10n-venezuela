from odoo import api, models


class AccountPaymentRegister(models.TransientModel):
    _inherit = "account.payment.register"

    @api.depends("l10n_ve_apply_advance")
    def _compute_l10n_ve_apply_igtf(self):
        result = super()._compute_l10n_ve_apply_igtf()
        self.filtered("l10n_ve_apply_advance").l10n_ve_apply_igtf = False
        return result

    @api.depends("l10n_ve_apply_advance")
    def _compute_l10n_ve_show_apply_igtf(self):
        result = super()._compute_l10n_ve_show_apply_igtf()
        self.filtered("l10n_ve_apply_advance").l10n_ve_show_apply_igtf = False
        return result

    def _l10n_ve_get_igtf_amounts_for_wizard(self):
        self.ensure_one()
        if self.l10n_ve_apply_advance:
            return 0.0, 0.0, 0.0
        return super()._l10n_ve_get_igtf_amounts_for_wizard()

    def _l10n_ve_adjust_advance_writeoff_for_igtf(self, vals):
        if (
            not vals.get("l10n_ve_apply_igtf")
            or vals.get("l10n_ve_igtf_included")
            or not self._uses_advance_payment_difference_handling()
        ):
            return vals
        advance_account = self._get_advance_account()
        igtf_currency = self.l10n_ve_igtf_amount_currency
        igtf_company = self.l10n_ve_igtf_amount_company_currency
        for line_vals in vals.get("write_off_line_vals", []):
            if line_vals.get("account_id") != advance_account.id:
                continue
            amount_currency = line_vals.get("amount_currency", 0.0)
            balance = line_vals.get("balance", 0.0)
            line_vals["amount_currency"] = (
                1.0 if amount_currency >= 0.0 else -1.0
            ) * max(abs(amount_currency) - igtf_currency, 0.0)
            line_vals["balance"] = (1.0 if balance >= 0.0 else -1.0) * max(
                abs(balance) - igtf_company, 0.0
            )
        return vals

    def _l10n_ve_prepare_advance_igtf_payment_vals(self, vals):
        if self.l10n_ve_apply_advance:
            vals.update(
                {
                    "l10n_ve_apply_igtf": False,
                    "l10n_ve_igtf_included": False,
                    "l10n_ve_igtf_cap_amount_company_currency": 0.0,
                }
            )
            return vals
        return self._l10n_ve_adjust_advance_writeoff_for_igtf(vals)

    def _create_payment_vals_from_wizard(self, batch_result):
        vals = super()._create_payment_vals_from_wizard(batch_result)
        return self._l10n_ve_prepare_advance_igtf_payment_vals(vals)

    def _create_payment_vals_from_batch(self, batch_result):
        vals = super()._create_payment_vals_from_batch(batch_result)
        return self._l10n_ve_prepare_advance_igtf_payment_vals(vals)
