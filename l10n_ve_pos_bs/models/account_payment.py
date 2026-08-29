# Copyright 2026 BWEALTHICS LLC
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import models
from odoo.exceptions import UserError


class AccountPayment(models.Model):
    _inherit = "account.payment"

    def _prepare_move_liquidity_lines(self, default_values):
        vals_list = super()._prepare_move_liquidity_lines(default_values)
        amount_ves = self.env.context.get("l10n_ve_pos_amount_ves")
        currency_id = self.env.context.get("l10n_ve_pos_currency_id")
        if not amount_ves or not currency_id:
            return vals_list
        if len(vals_list) != 1:
            raise UserError(
                self.env._(
                    "The VES denomination requires a single payment liquidity line."
                )
            )
        sign = -1 if default_values["amount_currency"] < 0 else 1
        vals_list[0].update(
            {
                "amount_currency": sign * abs(amount_ves),
                "currency_id": currency_id,
            }
        )
        return vals_list
