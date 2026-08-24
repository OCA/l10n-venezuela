import logging

from odoo import _, api, fields, models

from .res_partner import CUSTOMER_ADVANCE_ACCOUNT_TYPES, SUPPLIER_ADVANCE_ACCOUNT_TYPES

_logger = logging.getLogger(__name__)

_ADVANCE_ACCOUNT_TYPES = CUSTOMER_ADVANCE_ACCOUNT_TYPES + SUPPLIER_ADVANCE_ACCOUNT_TYPES


class AccountMove(models.Model):
    _inherit = "account.move"

    invoice_outstanding_advances_widget = fields.Binary(
        groups="account.group_account_invoice,account.group_account_readonly",
        compute="_compute_invoice_outstanding_advances_widget",
        exportable=False,
    )
    invoice_show_advances_widget = fields.Boolean(
        compute="_compute_invoice_outstanding_advances_widget",
    )
    invoice_has_outstanding_advances = fields.Boolean(
        compute="_compute_invoice_outstanding_advances_widget",
    )

    def _is_customer_advance_move(self):
        self.ensure_one()
        return self.is_sale_document(include_receipts=True)

    def _is_supplier_advance_move(self):
        self.ensure_one()
        return self.is_purchase_document(include_receipts=True)

    def _get_partner_advance_account(self):
        self.ensure_one()
        if self._is_supplier_advance_move():
            return self.env["res.partner"]._get_supplier_advance_account(
                self.commercial_partner_id, self.company_id
            )
        return self.env["res.partner"]._get_customer_advance_account(
            self.commercial_partner_id, self.company_id
        )

    def _line_has_advance_residual(self, line):
        if line.currency_id and not line.currency_id.is_zero(
            line.amount_residual_currency
        ):
            return True
        if not line.company_currency_id.is_zero(line.amount_residual):
            return True
        if line.account_id.account_type in _ADVANCE_ACCOUNT_TYPES:
            return not line.company_currency_id.is_zero(abs(line.balance))
        return False

    def _get_advance_line_amount_in_currency(self, line, currency):
        self.ensure_one()
        if line.currency_id == currency and not currency.is_zero(
            line.amount_residual_currency
        ):
            return abs(line.amount_residual_currency)
        if not line.company_currency_id.is_zero(line.amount_residual):
            return line.company_currency_id._convert(
                abs(line.amount_residual),
                currency,
                self.company_id,
                line.date,
            )
        return line.company_currency_id._convert(
            abs(line.balance),
            currency,
            self.company_id,
            line.date,
        )

    def _is_open_advance_line(self, line, advance_account):
        if line.account_id != advance_account:
            return False
        if not self._line_has_advance_residual(line):
            return False
        if line.account_id.account_type in SUPPLIER_ADVANCE_ACCOUNT_TYPES:
            return line.debit > line.credit or line.balance > 0
        if line.account_id.account_type in CUSTOMER_ADVANCE_ACCOUNT_TYPES:
            return line.credit > line.debit or line.balance < 0
        return line.balance < 0

    def _line_belongs_to_invoice_partner(self, line, partner):
        line_partner = line.partner_id or line.move_id.partner_id
        if not line_partner:
            return False
        return line_partner.commercial_partner_id == partner.commercial_partner_id

    def _get_outstanding_advance_lines(self, advance_account):
        self.ensure_one()
        partner = self.commercial_partner_id
        line_model = self.env["account.move.line"]
        base_domain = [
            ("account_id", "=", advance_account.id),
            ("parent_state", "=", "posted"),
            ("company_id", "=", self.company_id.id),
            ("reconciled", "=", False),
            ("display_type", "not in", ("line_section", "line_note")),
        ]
        lines_partner = line_model.search(
            base_domain + [("partner_id", "child_of", partner.id)]
        )
        lines_no_partner = line_model.search(
            base_domain
            + [
                ("partner_id", "=", False),
                ("move_id.partner_id", "child_of", partner.id),
            ]
        )
        lines = lines_partner | lines_no_partner
        payments = self.env["account.payment"].search(
            [
                ("partner_id", "child_of", partner.id),
                ("state", "in", ("paid", "in_process")),
                ("destination_account_id", "=", advance_account.id),
                ("company_id", "=", self.company_id.id),
            ]
        )
        lines_payment = self.env["account.move.line"]
        for payment in payments:
            if payment.move_id:
                lines_payment |= payment.move_id.line_ids.filtered(
                    lambda line: line.account_id == advance_account
                    and not line.reconciled
                )
        lines |= lines_payment

        _logger.info(
            "l10n_ve_payment_advance: factura %s partner %s cuenta %s (%s) | "
            "candidatos partner=%s sin_partner=%s pagos=%s total=%s",
            self.name,
            partner.id,
            advance_account.code,
            advance_account.id,
            len(lines_partner),
            len(lines_no_partner),
            len(payments),
            len(lines),
        )

        result = self.env["account.move.line"]
        for line in lines:
            reasons = []
            if not self._is_open_advance_line(line, advance_account):
                if line.account_id != advance_account:
                    reasons.append("cuenta_distinta")
                elif not self._line_has_advance_residual(line):
                    reasons.append("sin_saldo_ni_residual")
                else:
                    reasons.append("no_es_anticipo_abierto")
            if not self._line_belongs_to_invoice_partner(line, partner):
                reasons.append("partner_no_coincide")
            if reasons:
                _logger.info(
                    "l10n_ve_payment_advance:   descartada aml=%s move=%s "
                    "balance=%s residual=%s credit=%s debit=%s partner=%s "
                    "move_partner=%s reconcile_account=%s | %s",
                    line.id,
                    line.move_id.name,
                    line.balance,
                    line.amount_residual,
                    line.credit,
                    line.debit,
                    line.partner_id.id,
                    line.move_id.partner_id.id,
                    line.account_id.reconcile,
                    ", ".join(reasons),
                )
                continue
            _logger.info(
                "l10n_ve_payment_advance:   incluida aml=%s move=%s balance=%s "
                "residual=%s amount_currency=%s",
                line.id,
                line.move_id.name,
                line.balance,
                line.amount_residual,
                self._get_advance_line_amount_in_currency(line, self.currency_id),
            )
            result |= line
        _logger.info(
            "l10n_ve_payment_advance: factura %s anticipos incluidos=%s",
            self.name,
            len(result),
        )
        return result

    def _l10n_ve_should_show_advances_widget(self):
        self.ensure_one()
        if self.state != "posted" or self.payment_state not in ("not_paid", "partial"):
            return False
        return self._is_customer_advance_move() or self._is_supplier_advance_move()

    @api.depends("state", "payment_state", "move_type", "partner_id", "company_id")
    def _compute_invoice_outstanding_advances_widget(self):
        for move in self:
            move.invoice_show_advances_widget = False
            move.invoice_has_outstanding_advances = False
            move.invoice_outstanding_advances_widget = False
            if not move._l10n_ve_should_show_advances_widget():
                _logger.info(
                    "l10n_ve_payment_advance: factura %s sin widget | state=%s "
                    "payment_state=%s move_type=%s",
                    move.name,
                    move.state,
                    move.payment_state,
                    move.move_type,
                )
                continue
            move.invoice_show_advances_widget = True
            advance_account = move._get_partner_advance_account()
            empty_message = _("Sin anticipos pendientes")
            if not advance_account:
                empty_message = _(
                    "Configure una cuenta de anticipos en el contacto o en la compañía."
                )
                _logger.warning(
                    "l10n_ve_payment_advance: factura %s partner %s "
                    "sin cuenta anticipos",
                    move.name,
                    move.commercial_partner_id.id,
                )
            else:
                _logger.info(
                    "l10n_ve_payment_advance: factura %s cuenta anticipos %s (%s) "
                    "reconcile=%s",
                    move.name,
                    advance_account.code,
                    advance_account.id,
                    advance_account.reconcile,
                )
            widget_vals = {
                "outstanding": True,
                "content": [],
                "move_id": move.id,
                "title": _("Anticipos disponibles"),
                "empty_message": empty_message,
            }
            if advance_account:
                for line in move._get_outstanding_advance_lines(advance_account):
                    amount = move._get_advance_line_amount_in_currency(
                        line, move.currency_id
                    )
                    if move.currency_id.is_zero(amount):
                        _logger.info(
                            "l10n_ve_payment_advance:   aml=%s importe cero en %s",
                            line.id,
                            move.currency_id.name,
                        )
                        continue
                    widget_vals["content"].append(
                        {
                            "journal_name": line.ref or line.move_id.name,
                            "amount": amount,
                            "currency_id": move.currency_id.id,
                            "id": line.id,
                            "move_id": line.move_id.id,
                            "date": fields.Date.to_string(line.date),
                            "account_payment_id": line.payment_id.id,
                        }
                    )
            move.invoice_outstanding_advances_widget = widget_vals
            move.invoice_has_outstanding_advances = bool(widget_vals["content"])

    def action_open_advance_apply_register(self, advance_line_id):
        self.ensure_one()
        advance_line = self.env["account.move.line"].browse(advance_line_id).exists()
        if not advance_line:
            return False
        return {
            "name": _("Aplicar anticipo"),
            "type": "ir.actions.act_window",
            "res_model": "account.payment.register",
            "view_mode": "form",
            "views": [[False, "form"]],
            "target": "new",
            "context": {
                "active_model": "account.move",
                "active_ids": self.ids,
                "active_id": self.id,
                "l10n_ve_apply_advance": True,
                "default_l10n_ve_advance_line_id": advance_line.id,
            },
        }
