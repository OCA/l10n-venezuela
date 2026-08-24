from odoo import api, fields, models
from odoo.tools import float_is_zero


class PosSessionCashBox(models.Model):
    _name = "pos.session.cash.box"
    _description = "POS Session Cash Box"
    _order = "id"

    session_id = fields.Many2one(
        "pos.session",
        required=True,
        ondelete="cascade",
        index=True,
    )
    payment_method_id = fields.Many2one(
        "pos.payment.method",
        required=True,
        ondelete="restrict",
    )
    currency_id = fields.Many2one(
        "res.currency",
        compute="_compute_currency_id",
        store=True,
    )
    journal_id = fields.Many2one(
        "account.journal",
        related="payment_method_id.journal_id",
        store=True,
    )
    balance_start = fields.Monetary(
        currency_field="currency_id",
        default=0.0,
    )
    balance_end_real = fields.Monetary(
        currency_field="currency_id",
        default=0.0,
    )
    closing_difference = fields.Monetary(
        currency_field="currency_id",
        default=0.0,
        help="Counted minus expected at closing control time (before sales statement lines).",
    )
    balance_end = fields.Monetary(
        currency_field="currency_id",
        compute="_compute_balance_end",
    )
    difference = fields.Monetary(
        currency_field="currency_id",
        compute="_compute_balance_end",
    )
    is_primary = fields.Boolean(compute="_compute_is_primary")

    _sql_constraints = [
        (
            "session_payment_method_uniq",
            "unique(session_id, payment_method_id)",
            "A cash box already exists for this payment method in the session.",
        ),
    ]

    @api.depends("payment_method_id", "payment_method_id.payment_currency_id", "session_id.currency_id")
    def _compute_currency_id(self):
        for box in self:
            box.currency_id = (
                box.payment_method_id.payment_currency_id
                or box.session_id.currency_id
            )

    @api.depends("session_id.payment_method_ids", "payment_method_id")
    def _compute_is_primary(self):
        for box in self:
            primary = box.session_id.payment_method_ids.filtered(
                lambda pm: pm.type == "cash"
            )[:1]
            box.is_primary = bool(primary and box.payment_method_id == primary)

    @api.depends(
        "balance_start",
        "balance_end_real",
        "session_id.statement_line_ids.amount",
        "session_id.order_ids.payment_ids.amount",
        "session_id.order_ids.payment_ids.payment_currency_amount",
    )
    def _compute_balance_end(self):
        for box in self:
            expected = box._oca_get_expected_balance()
            box.balance_end = expected
            box.difference = box.balance_end_real - expected

    def _oca_is_cash_difference_statement_line(self, statement_line):
        """Cash difference lines use profit/loss accounts; cash in/out uses suspense."""
        self.ensure_one()
        journal = self.payment_method_id.journal_id
        profit_loss_accounts = journal.profit_account_id | journal.loss_account_id
        if not profit_loss_accounts:
            return False
        return bool(
            statement_line.move_id.line_ids.filtered(
                lambda move_line: move_line.account_id in profit_loss_accounts
            )
        )

    def _oca_get_expected_balance(self, include_all_statement_lines=False):
        self.ensure_one()
        session = self.session_id
        payment_method = self.payment_method_id
        payments = session._get_closed_orders().payment_ids.filtered(
            lambda payment: (
                payment.payment_method_id == payment_method
                and not payment.is_change
                and not float_is_zero(
                    payment.amount, precision_rounding=session.currency_id.rounding
                )
            )
        )
        payment_amount, _currency = session._oca_amount_in_payment_method_currency(
            payments,
            payment_method,
        )
        statement_lines = session.sudo().statement_line_ids.filtered(
            lambda line: line.journal_id == payment_method.journal_id
        )
        if not include_all_statement_lines:
            statement_lines = statement_lines.filtered(
                lambda line: not self._oca_is_cash_difference_statement_line(line)
            )
        moves_amount = sum(statement_lines.mapped("amount"))
        return self.currency_id.round(self.balance_start + payment_amount + moves_amount)
