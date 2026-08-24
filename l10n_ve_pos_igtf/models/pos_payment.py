from odoo import _, fields, models
from odoo.tools import float_is_zero, float_round


class PosPayment(models.Model):
    _inherit = "pos.payment"

    include_igtf = fields.Boolean()
    igtf_amount = fields.Float()
    foreign_igtf_amount = fields.Float()

    def _l10n_ve_pos_payment_applies_igtf_by_currency(self):
        self.ensure_one()
        if not self.company_id.l10n_ve_igtf_feature_active:
            return False
        allowed = self.company_id.l10n_ve_igtf_currency_ids
        if not allowed:
            return False
        pay_cur = (
            self.payment_currency_id
            or self.payment_method_id.payment_currency_id
            or self.currency_id
        )
        return bool(pay_cur) and pay_cur in allowed

    def _l10n_ve_pos_get_igtf_amount_from_posted_move(self):
        self.ensure_one()
        move = self.sudo().account_move_id
        if not move or move.state != "posted":
            return 0.0
        account = self.company_id.l10n_ve_igtf_account_id
        if not account:
            return 0.0
        lines = move.line_ids.filtered(lambda line: line.account_id == account)
        if not lines:
            return 0.0
        order = self.pos_order_id
        amt = sum(abs(line.amount_currency) for line in lines)
        if order:
            return order.currency_id.round(amt)
        return self.currency_id.round(amt)

    def _l10n_ve_pos_get_effective_igtf_amount(self):
        self.ensure_one()
        order = self.pos_order_id
        prec = order.currency_id.rounding if order else self.currency_id.rounding
        if float_is_zero(self.amount or 0.0, precision_rounding=prec):
            return 0.0
        if not float_is_zero(self.igtf_amount or 0.0, precision_rounding=prec):
            return self.igtf_amount
        if self.is_change:
            return 0.0
        from_move = self._l10n_ve_pos_get_igtf_amount_from_posted_move()
        if not float_is_zero(from_move, precision_rounding=prec):
            return from_move
        if (
            not self.include_igtf
            and not self._l10n_ve_pos_payment_applies_igtf_by_currency()
        ):
            return 0.0
        pct = (self.company_id.l10n_ve_igtf_percent or 0.0) / 100.0
        if not pct:
            return 0.0
        return float_round(
            (self.amount or 0.0) * pct,
            precision_rounding=prec,
        )

    def _l10n_ve_pos_get_effective_igtf_base_amount(self):
        self.ensure_one()
        if float_is_zero(
            self._l10n_ve_pos_get_effective_igtf_amount(),
            precision_rounding=self.pos_order_id.currency_id.rounding
            if self.pos_order_id
            else self.currency_id.rounding,
        ):
            return 0.0
        return abs(self.amount or 0.0)

    def _create_payment_moves(self, is_reverse=False):
        result = self.env["account.move"]
        credit_line_ids = []
        change_payment = self.filtered(
            lambda p: p.is_change and p.payment_method_id.type == "cash"
        )
        payment_to_change = self.filtered(
            lambda p: not p.is_change and p.payment_method_id.type == "cash"
        )[:1]
        payments = self
        if change_payment and payment_to_change:
            payments = self - change_payment

        AccountMoveLine = self.env["account.move.line"].with_context(
            check_move_validity=False
        )

        for payment in payments:
            order = payment.pos_order_id
            payment_method = payment.payment_method_id
            if payment_method.type == "pay_later" or float_is_zero(
                payment.amount, precision_rounding=order.currency_id.rounding
            ):
                continue
            accounting_partner = self.env["res.partner"]._find_accounting_partner(
                payment.partner_id
            )
            pos_session = order.session_id
            journal = pos_session.config_id.journal_id
            if change_payment and payment == payment_to_change:
                pos_payment_ids = payment.ids + change_payment.ids
                payment_amount = payment.amount + change_payment.amount
            else:
                pos_payment_ids = payment.ids
                payment_amount = payment.amount
            payment_move = (
                self.env["account.move"]
                .with_context(default_journal_id=journal.id)
                .create(
                    {
                        "journal_id": journal.id,
                        "date": fields.Date.context_today(order, order.date_order),
                        "ref": _(
                            "Invoice payment for %(order)s (%(account_move)s)"
                            " using %(payment_method)s",
                            order=order.name,
                            account_move=order.account_move.name,
                            payment_method=payment_method.name,
                        ),
                        "pos_payment_ids": pos_payment_ids,
                    }
                )
            )
            result |= payment_move
            payment.write({"account_move_id": payment_move.id})
            amounts = pos_session._update_amounts(
                {"amount": 0, "amount_converted": 0},
                {"amount": payment_amount},
                payment.payment_date,
            )
            igtf_account = payment.company_id.l10n_ve_igtf_account_id
            amount_igtf = float_round(
                payment.igtf_amount or 0.0,
                precision_rounding=order.currency_id.rounding,
            )
            if amount_igtf > amounts["amount"]:
                amount_igtf = amounts["amount"]
            use_igtf_split = (
                payment.include_igtf
                and amount_igtf
                and igtf_account
                and payment.company_id.l10n_ve_igtf_feature_active
            )
            if use_igtf_split:
                ratio = amount_igtf / amounts["amount"] if amounts["amount"] else 0.0
                igtf_conv = amounts["amount_converted"] * ratio
                main_amount = amounts["amount"] - amount_igtf
                main_conv = amounts["amount_converted"] - igtf_conv
                credit_line_vals = pos_session._credit_amounts(
                    {
                        "account_id": accounting_partner.with_company(
                            order.company_id
                        ).property_account_receivable_id.id,
                        "partner_id": accounting_partner.id,
                        "move_id": payment_move.id,
                    },
                    main_amount,
                    main_conv,
                )
                credit_igtf_vals = pos_session._credit_amounts(
                    {
                        "account_id": igtf_account.id,
                        "partner_id": accounting_partner.id,
                        "move_id": payment_move.id,
                    },
                    amount_igtf,
                    igtf_conv,
                )
            else:
                credit_line_vals = pos_session._credit_amounts(
                    {
                        "account_id": accounting_partner.with_company(
                            order.company_id
                        ).property_account_receivable_id.id,
                        "partner_id": accounting_partner.id,
                        "move_id": payment_move.id,
                    },
                    amounts["amount"],
                    amounts["amount_converted"],
                )
                credit_igtf_vals = None

            is_split_transaction = payment.payment_method_id.split_transactions
            if is_split_transaction and is_reverse:
                reversed_move_receivable_account_id = accounting_partner.with_company(
                    order.company_id
                ).property_account_receivable_id.id
            elif is_reverse:
                reversed_move_receivable_account_id = (
                    payment.payment_method_id.receivable_account_id.id
                    or self.company_id.account_default_pos_receivable_account_id.id
                )
            else:
                reversed_move_receivable_account_id = (
                    self.company_id.account_default_pos_receivable_account_id.id
                )
            debit_line_vals = pos_session._debit_amounts(
                {
                    "account_id": reversed_move_receivable_account_id,
                    "move_id": payment_move.id,
                    "partner_id": accounting_partner.id
                    if is_split_transaction and is_reverse
                    else False,
                },
                amounts["amount"],
                amounts["amount_converted"],
            )
            line_commands = [credit_line_vals, debit_line_vals]
            if credit_igtf_vals:
                line_commands.insert(1, credit_igtf_vals)
            lines = AccountMoveLine.create(line_commands)
            receivable_acc_id = accounting_partner.with_company(
                order.company_id
            ).property_account_receivable_id.id
            if amounts["amount_converted"] < 0:
                credit_line_ids += lines.filtered(
                    lambda line, acc=receivable_acc_id: (
                        line.debit and line.account_id.id == acc
                    )
                ).ids
            else:
                credit_line_ids += lines.filtered(
                    lambda line, acc=receivable_acc_id: (
                        line.credit and line.account_id.id == acc
                    )
                ).ids
            payment_move._post()
        return result.with_context(credit_line_ids=credit_line_ids)
