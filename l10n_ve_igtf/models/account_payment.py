# Copyright 2026 BWEALTHICS LLC
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models
from odoo.exceptions import UserError


class AccountPayment(models.Model):
    _inherit = "account.payment"

    l10n_ve_igtf_available = fields.Boolean(
        related="journal_id.l10n_ve_igtf_enabled",
        string="IGTF Available",
    )
    l10n_ve_igtf_apply = fields.Boolean(
        string="Apply IGTF",
        copy=False,
        help="Select this only after confirming that this specific transaction "
        "is subject to IGTF.",
    )
    l10n_ve_igtf_rate = fields.Float(
        string="IGTF Rate (%)",
        compute="_compute_l10n_ve_igtf_rate",
        store=True,
        readonly=False,
        precompute=True,
        help="Rate stored on this payment for historical traceability.",
    )
    l10n_ve_igtf_amount = fields.Monetary(
        string="IGTF Amount",
        currency_field="currency_id",
        compute="_compute_l10n_ve_igtf_amount",
        store=True,
    )

    @api.depends("company_id")
    def _compute_l10n_ve_igtf_rate(self):
        for payment in self:
            payment.l10n_ve_igtf_rate = payment.company_id.l10n_ve_igtf_rate

    @api.depends(
        "amount",
        "currency_id",
        "l10n_ve_igtf_apply",
        "l10n_ve_igtf_rate",
    )
    def _compute_l10n_ve_igtf_amount(self):
        for payment in self:
            amount = (
                payment.amount * payment.l10n_ve_igtf_rate / 100.0
                if payment.l10n_ve_igtf_apply
                else 0.0
            )
            payment.l10n_ve_igtf_amount = (
                payment.currency_id.round(amount) if payment.currency_id else amount
            )

    @api.onchange("journal_id")
    def _onchange_l10n_ve_igtf_journal_id(self):
        if not self.l10n_ve_igtf_available:
            self.l10n_ve_igtf_apply = False

    def _prepare_move_withholding_lines(self, default_values):
        lines = super()._prepare_move_withholding_lines(default_values)
        if not self.l10n_ve_igtf_apply:
            return lines

        self._l10n_ve_validate_igtf()
        amount_currency = self.l10n_ve_igtf_amount
        sign = 1 if self.payment_type == "outbound" else -1
        account = (
            self.company_id.l10n_ve_igtf_expense_account_id
            if self.payment_type == "outbound"
            else self.company_id.l10n_ve_igtf_perception_account_id
        )
        signed_amount_currency = sign * amount_currency
        balance = self.currency_id._convert(
            signed_amount_currency,
            self.company_id.currency_id,
            self.company_id,
            self.date,
        )
        lines.append(
            {
                "name": self.env._("IGTF %(rate)s%%", rate=self.l10n_ve_igtf_rate),
                "date_maturity": self.date,
                "partner_id": self.partner_id.id,
                "account_id": account.id,
                "currency_id": self.currency_id.id,
                "amount_currency": signed_amount_currency,
                "balance": balance,
                "l10n_ve_igtf_line": True,
            }
        )
        return lines

    def _prepare_move_lines_per_type(
        self, write_off_line_vals=None, force_balance=None
    ):
        if self.l10n_ve_igtf_apply and write_off_line_vals:
            raise UserError(
                self.env._(
                    "IGTF cannot be combined with a payment-difference write-off. "
                    "Keep the difference open and record it separately."
                )
            )
        return super()._prepare_move_lines_per_type(
            write_off_line_vals=write_off_line_vals,
            force_balance=force_balance,
        )

    def _synchronize_to_moves(self, changed_fields):
        if any(
            field_name in changed_fields
            for field_name in self._get_trigger_fields_to_synchronize()
        ):
            igtf_lines = self.move_id.filtered(
                lambda move: move.state == "draft"
            ).line_ids.filtered("l10n_ve_igtf_line")
            igtf_lines.with_context(check_move_validity=False).unlink()
        return super()._synchronize_to_moves(changed_fields)

    @api.model
    def _get_trigger_fields_to_synchronize(self):
        return (
            *super()._get_trigger_fields_to_synchronize(),
            "l10n_ve_igtf_apply",
            "l10n_ve_igtf_rate",
        )

    def _l10n_ve_validate_igtf(self):
        self.ensure_one()
        if not self.l10n_ve_igtf_available:
            raise UserError(self.env._("Enable IGTF on the payment journal first."))
        if self.l10n_ve_igtf_rate <= 0:
            raise UserError(self.env._("The IGTF rate must be greater than zero."))
        if self.payment_type == "outbound":
            if not self.company_id.l10n_ve_igtf_expense_account_id:
                raise UserError(self.env._("Configure the IGTF expense account first."))
            return

        company = self.company_id
        if not company.l10n_ve_igtf_perception_agent:
            raise UserError(
                self.env._(
                    "The company must be an IGTF perception agent for incoming "
                    "payments."
                )
            )
        if (
            company.l10n_ve_igtf_perception_agent_date
            and self.date < company.l10n_ve_igtf_perception_agent_date
        ):
            raise UserError(
                self.env._(
                    "The payment date is before the IGTF perception designation date."
                )
            )
        if not company.l10n_ve_igtf_perception_account_id:
            raise UserError(self.env._("Configure the IGTF perception account first."))
