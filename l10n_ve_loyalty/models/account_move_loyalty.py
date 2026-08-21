# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, models
from odoo.exceptions import UserError
from odoo.tools import float_is_zero


class AccountMove(models.Model):
    _inherit = "account.move"

    def _l10n_ve_apply_loyalty_global_discount(
        self,
        amount,
        reason=None,
        discount_type="fixed",
        discount_percentage=0.0,
        amount_base="untaxed",
    ):
        """Create a VE global discount from a loyalty/POS reward amount."""
        self.ensure_one()
        if self.country_code != "VE" or not self.is_invoice(include_receipts=True):
            return self.env["l10n.ve.account.move.discount"]
        currency = self.currency_id
        if float_is_zero(amount, precision_rounding=currency.rounding):
            return self.env["l10n.ve.account.move.discount"]
        if reason is None:
            reason = self.env["l10n.ve.discount.reason"]._l10n_ve_get_default()
        if not reason:
            raise UserError(_("Configure at least one Venezuela discount reason."))
        return self.env["l10n.ve.account.move.discount"].with_context(
            l10n_ve_skip_global_discount_access_check=True,
        ).create(
            {
                "move_id": self.id,
                "reason_id": reason.id,
                "amount": currency.round(abs(amount)),
                "discount_type": discount_type,
                "discount_percentage": discount_percentage
                if discount_type == "percentage"
                else 0.0,
                "amount_base": amount_base or "untaxed",
            }
        )
