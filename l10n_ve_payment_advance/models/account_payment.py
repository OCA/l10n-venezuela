from odoo import api, fields, models

from .res_partner import CUSTOMER_ADVANCE_ACCOUNT_TYPES, SUPPLIER_ADVANCE_ACCOUNT_TYPES

_DESTINATION_ACCOUNT_TYPES = (
    "asset_receivable",
    "liability_payable",
    *CUSTOMER_ADVANCE_ACCOUNT_TYPES,
    *SUPPLIER_ADVANCE_ACCOUNT_TYPES,
)


class AccountPayment(models.Model):
    _inherit = "account.payment"

    destination_account_id = fields.Many2one(
        domain="[('account_type', 'in', %s), ('deprecated', '=', False)]"  # noqa: UP031
        % (_DESTINATION_ACCOUNT_TYPES,)
    )
    payment_has_invoice_lines = fields.Boolean(
        string="Pago contra líneas de factura",
        default=False,
        copy=False,
        help=(
            "Indica que el pago se creó desde el asistente de registro de "
            "pagos contra líneas de factura."
        ),
    )
    l10n_ve_is_advance_application = fields.Boolean(
        string="Aplicación de anticipo",
        copy=False,
    )
    l10n_ve_advance_line_ids = fields.Many2many(
        comodel_name="account.move.line",
        relation="account_payment_advance_line_rel",
        column1="payment_id",
        column2="line_id",
        string="Líneas de anticipo",
        copy=False,
    )

    def _get_customer_advance_account(self):
        self.ensure_one()
        return self.env["res.partner"]._get_customer_advance_account(
            self.partner_id, self.company_id
        )

    def _get_supplier_advance_account(self):
        self.ensure_one()
        return self.env["res.partner"]._get_supplier_advance_account(
            self.partner_id, self.company_id
        )

    def _get_advance_account(self):
        self.ensure_one()
        if self.partner_type == "supplier":
            return self._get_supplier_advance_account()
        return self._get_customer_advance_account()

    def _should_post_to_customer_advance_account(self):
        self.ensure_one()
        if self.partner_type != "customer" or self.payment_type != "inbound":
            return False
        if self.payment_has_invoice_lines:
            return False
        if self.reconciled_invoice_ids:
            return False
        return bool(self._get_customer_advance_account())

    def _should_post_to_supplier_advance_account(self):
        self.ensure_one()
        if self.partner_type != "supplier" or self.payment_type != "outbound":
            return False
        if self.payment_has_invoice_lines:
            return False
        if self.reconciled_bill_ids:
            return False
        return bool(self._get_supplier_advance_account())

    @api.depends(
        "payment_method_line_id",
        "l10n_ve_is_advance_application",
        "partner_id",
        "partner_type",
        "company_id",
    )
    def _compute_outstanding_account_id(self):
        others = self.filtered(lambda pay: not pay.l10n_ve_is_advance_application)
        for payment in others:
            payment.outstanding_account_id = (
                payment.payment_method_line_id.payment_account_id
            )
        for payment in self.filtered("l10n_ve_is_advance_application"):
            payment.outstanding_account_id = payment._get_advance_account()

    @api.depends(
        "journal_id",
        "partner_id",
        "partner_type",
        "payment_type",
        "payment_has_invoice_lines",
    )
    def _compute_destination_account_id(self):
        result = super()._compute_destination_account_id()
        for payment in self:
            if payment._should_post_to_customer_advance_account():
                payment.destination_account_id = payment._get_customer_advance_account()
            elif payment._should_post_to_supplier_advance_account():
                payment.destination_account_id = payment._get_supplier_advance_account()
        return result

    def _l10n_ve_get_advance_liquidity_lines(self):
        self.ensure_one()
        advance_account = self.outstanding_account_id
        if not advance_account:
            return self.env["account.move.line"]
        liquidity_lines, _counterpart_lines, _writeoff_lines = self._seek_for_lines()
        payment_advance_lines = liquidity_lines.filtered(
            lambda line: line.account_id == advance_account
        )
        if payment_advance_lines:
            return payment_advance_lines
        return self.move_id.line_ids.filtered(
            lambda line: line.account_id == advance_account and not line.reconciled
        )

    def _l10n_ve_reconcile_advance_source_lines(self):
        for payment in self.filtered("l10n_ve_is_advance_application"):
            advance_lines = payment.l10n_ve_advance_line_ids.filtered(
                lambda line: not line.reconciled
            )
            if not advance_lines:
                continue
            payment_advance_lines = (
                payment._l10n_ve_get_advance_liquidity_lines().filtered(
                    lambda line: not line.reconciled
                )
            )
            if payment_advance_lines and advance_lines:
                (payment_advance_lines + advance_lines).reconcile()
