# Copyright 2026 BWEALTHICS LLC
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class PosPayment(models.Model):
    _inherit = "pos.payment"

    l10n_ve_amount_ves = fields.Float(
        string="Amount in VES",
        digits=(16, 2),
        help="Exact bolivar amount received or refunded, with the same sign as "
        "the POS payment.",
    )
    l10n_ve_ves_rate = fields.Float(
        string="VES Exchange Rate",
        digits=(16, 6),
        help="VES units per unit of POS currency when the payment was captured.",
    )
    l10n_ve_pos_amount = fields.Monetary(
        string="Captured POS Amount",
        currency_field="currency_id",
        help="Payment amount in the POS currency when the VES amount was captured.",
    )

    @api.constrains(
        "amount",
        "l10n_ve_amount_ves",
        "l10n_ve_pos_amount",
        "l10n_ve_ves_rate",
        "payment_method_id",
        "payment_ref_no",
    )
    def _check_l10n_ve_ves_capture(self):
        ves = self.env.ref("base.VES")
        for payment in self.filtered("payment_method_id.l10n_ve_ves_tender"):
            if payment.currency_id.is_zero(payment.amount):
                if not ves.is_zero(
                    payment.l10n_ve_amount_ves
                ) or not payment.currency_id.is_zero(payment.l10n_ve_pos_amount):
                    raise ValidationError(
                        self.env._("A zero POS payment cannot contain a VES amount.")
                    )
                continue
            if ves.is_zero(payment.l10n_ve_amount_ves):
                raise ValidationError(
                    self.env._("Enter the exact VES amount for the payment.")
                )
            if (payment.amount > 0) != (payment.l10n_ve_amount_ves > 0):
                raise ValidationError(
                    self.env._(
                        "The VES amount must have the same sign as the POS payment."
                    )
                )
            if payment.currency_id.compare_amounts(
                payment.amount, payment.l10n_ve_pos_amount
            ):
                raise ValidationError(
                    self.env._(
                        "Capture the VES amount again after changing the POS amount."
                    )
                )
            if payment.l10n_ve_ves_rate <= 0:
                raise ValidationError(
                    self.env._("The VES exchange rate must be greater than zero.")
                )
            if (
                payment.payment_method_id.l10n_ve_require_reference
                and not (payment.payment_ref_no or "").strip()
            ):
                raise ValidationError(
                    self.env._("Enter the transaction reference for the VES payment.")
                )
