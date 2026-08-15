# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class L10nVeAccountMovePostDiscountWizard(models.TransientModel):
    _name = "l10n.ve.account.move.post.discount.wizard"
    _inherit = "l10n.ve.account.move.discount.wizard"
    _description = "Venezuela post-invoice discount credit note wizard"

    def action_create_credit_note(self):
        return self.action_apply_discount()
