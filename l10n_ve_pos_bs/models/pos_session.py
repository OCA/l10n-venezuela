# Copyright 2026 BWEALTHICS LLC
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import models
from odoo.exceptions import UserError


class PosSession(models.Model):
    _inherit = "pos.session"

    def _create_bank_payment_moves(self, data):
        payment_method_diffs = data.get("bank_payment_method_diffs", {})
        for payment_method in self.payment_method_ids.filtered("l10n_ve_ves_tender"):
            difference = payment_method_diffs.get(payment_method.id, 0.0)
            if not self.currency_id.is_zero(difference):
                raise UserError(
                    self.env._(
                        "A VES tender cannot be closed with a payment difference. "
                        "Correct the tender amount before closing the session."
                    )
                )
        return super()._create_bank_payment_moves(data)

    def _l10n_ve_ves_context(self, payments, session_amount, diff_amount=0.0):
        self.ensure_one()
        if not self.currency_id.is_zero(diff_amount):
            raise UserError(
                self.env._(
                    "A VES tender cannot be closed with a payment difference. "
                    "Correct the tender amount before closing the session."
                )
            )
        ves = self.env.ref("base.VES")
        if ves == self.company_id.currency_id:
            raise UserError(
                self.env._(
                    "VES tender tracking is only needed when VES is a foreign currency."
                )
            )
        amount_ves = ves.round(sum(payments.mapped("l10n_ve_amount_ves")))
        if self.currency_id.is_zero(session_amount):
            if not ves.is_zero(amount_ves):
                raise UserError(
                    self.env._(
                        "The VES tender has a zero POS-currency balance but a non-zero "
                        "VES balance. Split refunds into a separate session."
                    )
                )
            return {}
        if ves.is_zero(amount_ves):
            raise UserError(
                self.env._("The exact VES amount is missing from the POS payments.")
            )
        if (session_amount > 0) != (amount_ves > 0):
            raise UserError(
                self.env._(
                    "The VES total must have the same sign as the POS-currency total."
                )
            )
        return {
            "l10n_ve_pos_amount_ves": abs(amount_ves),
            "l10n_ve_pos_currency_id": ves.id,
        }

    def _l10n_ve_annotate_payment_references(self, move_line, payments):
        references = [
            reference.strip()
            for reference in payments.mapped("payment_ref_no")
            if reference and reference.strip()
        ]
        if references and move_line:
            move = move_line.move_id
            move.ref = self.env._(
                "%(reference)s - References: %(references)s",
                reference=move.ref or "",
                references=", ".join(references),
            )

    def _create_combine_account_payment(self, payment_method, amounts, diff_amount):
        if payment_method.l10n_ve_ves_tender:
            payments = self._get_closed_orders().payment_ids.filtered(
                lambda payment: payment.payment_method_id == payment_method
                and not payment.currency_id.is_zero(payment.amount)
            )
            context = self._l10n_ve_ves_context(
                payments, amounts["amount"], diff_amount
            )
            move_line = super(
                PosSession, self.with_context(**context)
            )._create_combine_account_payment(payment_method, amounts, diff_amount)
            self._l10n_ve_annotate_payment_references(move_line, payments)
            return move_line
        return super()._create_combine_account_payment(
            payment_method, amounts, diff_amount
        )

    def _create_split_account_payments(self, payment_amounts_list):
        regular_items = []
        ves_items = []
        for payment, amounts in payment_amounts_list:
            if payment.payment_method_id.l10n_ve_ves_tender:
                ves_items.append((payment, amounts))
            else:
                regular_items.append((payment, amounts))

        payment_to_line = super()._create_split_account_payments(regular_items)
        for payment, amounts in ves_items:
            context = self._l10n_ve_ves_context(payment, amounts["amount"])
            result = super(
                PosSession, self.with_context(**context)
            )._create_split_account_payments([(payment, amounts)])
            self._l10n_ve_annotate_payment_references(result.get(payment), payment)
            payment_to_line.update(result)
        return payment_to_line
