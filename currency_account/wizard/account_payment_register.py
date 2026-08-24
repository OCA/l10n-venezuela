from odoo import api, models


class AccountPaymentRegister(models.TransientModel):
    _inherit = "account.payment.register"

    @api.depends("early_payment_discount_mode")
    def _compute_payment_difference_handling(self):
        super()._compute_payment_difference_handling()
        for wizard in self:
            if wizard.can_edit_wizard:
                wizard.payment_difference_handling = "open"
