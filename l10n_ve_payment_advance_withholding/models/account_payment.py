from odoo import models


class AccountPayment(models.Model):
    _inherit = "account.payment"

    def _should_post_to_customer_advance_account(self):
        self.ensure_one()
        if self.is_retention:
            return False
        return super()._should_post_to_customer_advance_account()

    def _should_post_to_supplier_advance_account(self):
        self.ensure_one()
        if self.is_retention:
            return False
        return super()._should_post_to_supplier_advance_account()
