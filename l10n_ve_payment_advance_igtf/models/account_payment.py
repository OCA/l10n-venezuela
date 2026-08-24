from odoo import api, models


class AccountPayment(models.Model):
    _inherit = "account.payment"

    @api.depends("l10n_ve_is_advance_application")
    def _compute_l10n_ve_show_apply_igtf(self):
        result = super()._compute_l10n_ve_show_apply_igtf()
        self.filtered("l10n_ve_is_advance_application").l10n_ve_show_apply_igtf = False
        return result

    def _l10n_ve_get_igtf_amounts(self):
        self.ensure_one()
        if self.l10n_ve_is_advance_application:
            return 0.0, 0.0
        return super()._l10n_ve_get_igtf_amounts()
