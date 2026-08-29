# Copyright 2026 BWEALTHICS LLC
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import Command, api, fields, models
from odoo.exceptions import UserError


class AccountPaymentRegister(models.TransientModel):
    _inherit = "account.payment.register"

    l10n_ve_igtf_available = fields.Boolean(
        compute="_compute_l10n_ve_igtf_available",
    )
    l10n_ve_igtf_apply = fields.Boolean(
        string="Apply IGTF",
        help="Select this only after confirming that this specific transaction "
        "is subject to IGTF.",
    )
    l10n_ve_igtf_rate = fields.Float(
        related="company_id.l10n_ve_igtf_rate",
    )
    l10n_ve_igtf_amount = fields.Monetary(
        string="IGTF Amount",
        currency_field="currency_id",
        compute="_compute_l10n_ve_igtf_amount",
    )

    @api.depends("journal_id.l10n_ve_igtf_enabled", "currency_id", "line_ids")
    def _compute_l10n_ve_igtf_available(self):
        for wizard in self:
            wizard.l10n_ve_igtf_available = (
                wizard.journal_id.l10n_ve_igtf_enabled
                and not wizard.currency_id._l10n_ve_is_bolivar()
                and bool(wizard._l10n_ve_get_igtf_invoices(wizard.line_ids))
            )

    @api.depends(
        "amount",
        "currency_id",
        "l10n_ve_igtf_apply",
        "l10n_ve_igtf_rate",
    )
    def _compute_l10n_ve_igtf_amount(self):
        for wizard in self:
            amount = (
                wizard.amount * wizard.l10n_ve_igtf_rate / 100.0
                if wizard.l10n_ve_igtf_apply
                else 0.0
            )
            wizard.l10n_ve_igtf_amount = (
                wizard.currency_id.round(amount) if wizard.currency_id else amount
            )

    @api.onchange("journal_id", "currency_id")
    def _onchange_l10n_ve_igtf_available(self):
        if not self.l10n_ve_igtf_available:
            self.l10n_ve_igtf_apply = False

    def _create_payment_vals_from_wizard(self, batch_result):
        vals = super()._create_payment_vals_from_wizard(batch_result)
        return self._l10n_ve_add_igtf_payment_vals(vals, batch_result)

    def _create_payment_vals_from_batch(self, batch_result):
        vals = super()._create_payment_vals_from_batch(batch_result)
        return self._l10n_ve_add_igtf_payment_vals(vals, batch_result)

    def _l10n_ve_get_igtf_invoices(self, lines):
        return lines.move_id.filtered(
            lambda move: move.is_invoice(include_receipts=True)
        )

    def _l10n_ve_add_igtf_payment_vals(self, vals, batch_result):
        self.ensure_one()
        if self.l10n_ve_igtf_apply and vals.get("write_off_line_vals"):
            raise UserError(
                self.env._(
                    "IGTF cannot be combined with a payment-difference write-off. "
                    "Keep the difference open and record it separately."
                )
            )
        vals.update(
            {
                "l10n_ve_igtf_apply": self.l10n_ve_igtf_apply,
                "l10n_ve_igtf_rate": self.l10n_ve_igtf_rate,
            }
        )
        if self.l10n_ve_igtf_apply:
            # Core links the invoices only after posting (matched_payment_ids
            # in _reconcile_payments); link them now so the payment is known
            # to settle invoices when its IGTF line is validated.
            invoices = self._l10n_ve_get_igtf_invoices(batch_result["lines"])
            vals["invoice_ids"] = [Command.set(invoices.ids)]
        return vals
