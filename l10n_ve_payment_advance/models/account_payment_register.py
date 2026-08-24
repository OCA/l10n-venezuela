from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError


class AccountPaymentRegister(models.TransientModel):
    _inherit = "account.payment.register"

    payment_difference_handling = fields.Selection(
        selection_add=[("advance", "Mantener como anticipo")],
        ondelete={"advance": "cascade"},
    )
    show_advance_difference_handling = fields.Boolean(
        compute="_compute_show_advance_difference_handling",
    )
    l10n_ve_apply_advance = fields.Boolean(
        string="Aplicar anticipo a factura",
        default=lambda self: bool(self.env.context.get("l10n_ve_apply_advance")),
    )
    l10n_ve_advance_line_id = fields.Many2one(
        comodel_name="account.move.line",
        string="Línea de anticipo",
        domain="[('reconciled', '=', False), ('parent_state', '=', 'posted')]",
        check_company=True,
    )
    l10n_ve_advance_amount_available = fields.Monetary(
        string="Anticipo disponible",
        currency_field="currency_id",
        compute="_compute_l10n_ve_advance_amount_available",
    )
    l10n_ve_invoice_amount_residual = fields.Monetary(
        string="Importe pendiente factura",
        currency_field="currency_id",
        compute="_compute_l10n_ve_advance_amount_available",
    )

    payment_difference_handling_overpay = fields.Selection(
        selection=[
            ("advance", "Mantener como anticipo"),
            ("reconcile", "Marcar como totalmente pagado"),
        ],
        string="Gestión de la diferencia de pago",
        compute="_compute_payment_difference_handling_overpay",
        inverse="_inverse_payment_difference_handling_overpay",
        readonly=False,
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

    def _get_advance_line_residual_in_wizard_currency(self, advance_line):
        self.ensure_one()
        payment_date = self.payment_date or fields.Date.context_today(self)
        if (
            advance_line.currency_id == self.currency_id
            and not self.currency_id.is_zero(advance_line.amount_residual_currency)
        ):
            return abs(advance_line.amount_residual_currency)
        if not advance_line.company_currency_id.is_zero(advance_line.amount_residual):
            return advance_line.company_currency_id._convert(
                abs(advance_line.amount_residual),
                self.currency_id,
                self.company_id,
                payment_date,
            )
        return advance_line.company_currency_id._convert(
            abs(advance_line.balance),
            self.currency_id,
            self.company_id,
            payment_date,
        )

    def _get_invoice_residual_in_wizard_currency(self):
        self.ensure_one()
        if not self.line_ids:
            return 0.0
        if self.line_ids.currency_id == self.currency_id:
            return abs(sum(self.line_ids.mapped("amount_residual_currency")))
        return self.company_currency_id._convert(
            abs(sum(self.line_ids.mapped("amount_residual"))),
            self.currency_id,
            self.company_id,
            self.payment_date or fields.Date.context_today(self),
        )

    @api.depends(
        "l10n_ve_advance_line_id",
        "line_ids",
        "currency_id",
        "payment_date",
        "company_id",
    )
    def _compute_l10n_ve_advance_amount_available(self):
        for wizard in self:
            advance_amount = 0.0
            invoice_residual = 0.0
            if wizard.l10n_ve_advance_line_id:
                advance_amount = wizard._get_advance_line_residual_in_wizard_currency(
                    wizard.l10n_ve_advance_line_id
                )
            if wizard.line_ids:
                invoice_residual = wizard._get_invoice_residual_in_wizard_currency()
            wizard.l10n_ve_advance_amount_available = advance_amount
            wizard.l10n_ve_invoice_amount_residual = invoice_residual

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if self.env.context.get("l10n_ve_apply_advance"):
            res["l10n_ve_apply_advance"] = True
            advance_line_id = self.env.context.get("default_l10n_ve_advance_line_id")
            if advance_line_id and "l10n_ve_advance_line_id" in fields_list:
                res["l10n_ve_advance_line_id"] = advance_line_id
        return res

    @api.depends("line_ids", "l10n_ve_apply_advance")
    def _compute_from_lines(self):
        result = super()._compute_from_lines()
        for wizard in self.filtered("l10n_ve_apply_advance"):
            if len(wizard.batches) == 1:
                wizard.can_edit_wizard = True
        return result

    def _get_advance_partner_label(self):
        self.ensure_one()
        return _("proveedor") if self.partner_type == "supplier" else _("cliente")

    @api.constrains("amount", "l10n_ve_apply_advance", "l10n_ve_advance_line_id")
    def _check_l10n_ve_advance_apply_amount(self):
        for wizard in self.filtered("l10n_ve_apply_advance"):
            if not wizard.l10n_ve_advance_line_id:
                raise UserError(_("Seleccione la línea de anticipo a aplicar."))
            advance_account = wizard._get_advance_account()
            advance_line = wizard.l10n_ve_advance_line_id
            partner_label = wizard._get_advance_partner_label()
            if advance_account and advance_line.account_id != advance_account:
                raise UserError(
                    _(
                        "La línea seleccionada no pertenece a la cuenta "
                        "de anticipos del %(partner)s.",
                        partner=partner_label,
                    )
                )
            if (
                advance_line.partner_id.commercial_partner_id
                != wizard.partner_id.commercial_partner_id
            ):
                raise UserError(
                    _(
                        "La línea de anticipo no corresponde al %(partner)s "
                        "de la factura.",
                        partner=partner_label,
                    )
                )
            if wizard.currency_id.compare_amounts(wizard.amount, 0.0) <= 0:
                raise UserError(_("El importe a aplicar debe ser mayor que cero."))
            if (
                wizard.currency_id.compare_amounts(
                    wizard.amount, wizard.l10n_ve_advance_amount_available
                )
                > 0
            ):
                raise UserError(
                    _(
                        "No puede aplicar más del anticipo disponible (%(amount)s).",
                        amount=wizard.l10n_ve_advance_amount_available,
                    )
                )
            if (
                wizard.currency_id.compare_amounts(
                    wizard.amount, wizard.l10n_ve_invoice_amount_residual
                )
                > 0
            ):
                raise UserError(
                    _(
                        "No puede aplicar más del importe pendiente de la "
                        "factura (%(amount)s).",
                        amount=wizard.l10n_ve_invoice_amount_residual,
                    )
                )

    def _is_advance_overpayment_difference(self):
        self.ensure_one()
        if self.currency_id.compare_amounts(self.payment_difference, 0.0) >= 0:
            return False
        if self.partner_type == "customer" and self.payment_type == "inbound":
            return True
        if self.partner_type == "supplier" and self.payment_type == "outbound":
            return True
        return False

    @api.depends(
        "partner_type",
        "payment_type",
        "payment_difference",
        "partner_id",
        "company_id",
    )
    def _compute_show_advance_difference_handling(self):
        for wizard in self:
            wizard.show_advance_difference_handling = bool(
                wizard._is_advance_overpayment_difference()
                and wizard._get_advance_account()
            )

    @api.depends("payment_difference_handling", "show_advance_difference_handling")
    def _compute_payment_difference_handling_overpay(self):
        for wizard in self:
            if wizard.payment_difference_handling == "reconcile":
                wizard.payment_difference_handling_overpay = "reconcile"
            elif wizard.show_advance_difference_handling:
                wizard.payment_difference_handling_overpay = "advance"
            else:
                wizard.payment_difference_handling_overpay = False

    def _inverse_payment_difference_handling_overpay(self):
        for wizard in self:
            if wizard.payment_difference_handling_overpay:
                wizard.payment_difference_handling = (
                    wizard.payment_difference_handling_overpay
                )

    @api.depends(
        "early_payment_discount_mode",
        "can_edit_wizard",
        "show_advance_difference_handling",
        "payment_difference",
        "l10n_ve_apply_advance",
    )
    def _compute_payment_difference_handling(self):
        for wizard in self:
            if wizard.l10n_ve_apply_advance:
                wizard.payment_difference_handling = "reconcile"
                continue
            if not wizard.can_edit_wizard:
                wizard.payment_difference_handling = False
            elif wizard.early_payment_discount_mode:
                wizard.payment_difference_handling = "reconcile"
            elif wizard.show_advance_difference_handling:
                if wizard.payment_difference_handling not in (
                    "advance",
                    "reconcile",
                ):
                    wizard.payment_difference_handling = "advance"
            elif wizard.payment_difference_handling == "advance":
                wizard.payment_difference_handling = "open"
            elif wizard.payment_difference_handling not in ("open", "reconcile"):
                wizard.payment_difference_handling = "open"

    def _uses_advance_payment_difference_handling(self):
        self.ensure_one()
        return self.payment_difference_handling == "advance"

    def _should_use_advance_for_payment_difference(self):
        self.ensure_one()
        if self.early_payment_discount_mode or self.writeoff_is_exchange_account:
            return False
        if not self._get_advance_account():
            return False
        if not self._is_advance_overpayment_difference():
            return False
        return self.payment_difference_handling in ("advance", "reconcile")

    def _prepare_advance_writeoff_defaults(self):
        self.ensure_one()
        advance_account = self._get_advance_account()
        if not advance_account:
            raise UserError(
                _(
                    "Configure una cuenta de anticipos en el contacto "
                    "o en los ajustes de la compañía."
                )
            )
        if not self.writeoff_account_id:
            self.writeoff_account_id = advance_account
        if self.writeoff_label in (False, "Write-Off"):
            if self.partner_type == "supplier":
                self.writeoff_label = _("Anticipo de proveedor")
            else:
                self.writeoff_label = _("Anticipo de cliente")

    def _apply_advance_account_to_writeoff_lines(self, payment_vals):
        if not self._should_use_advance_for_payment_difference():
            return payment_vals
        advance_account = self._get_advance_account()
        for line_vals in payment_vals.get("write_off_line_vals", []):
            line_vals["account_id"] = advance_account.id
        return payment_vals

    def _prepare_l10n_ve_advance_application_payment_vals(self, payment_vals):
        self.ensure_one()
        advance_account = self._get_advance_account()
        if not advance_account:
            raise UserError(
                _(
                    "Configure una cuenta de anticipos en el contacto "
                    "o en los ajustes de la compañía."
                )
            )
        payment_vals.update(
            {
                "l10n_ve_is_advance_application": True,
                "l10n_ve_advance_line_ids": [
                    Command.set(self.l10n_ve_advance_line_id.ids)
                ],
                "outstanding_account_id": advance_account.id,
                "payment_has_invoice_lines": True,
                "write_off_line_vals": [],
            }
        )
        return payment_vals

    def _create_payment_vals_from_wizard(self, batch_result):
        if self.l10n_ve_apply_advance:
            payment_vals = super()._create_payment_vals_from_wizard(batch_result)
            return self._prepare_l10n_ve_advance_application_payment_vals(payment_vals)
        advance_mode = self._uses_advance_payment_difference_handling()
        previous_handling = self.payment_difference_handling
        if advance_mode:
            self._prepare_advance_writeoff_defaults()
            self.payment_difference_handling = "reconcile"
        payment_vals = super()._create_payment_vals_from_wizard(batch_result)
        if advance_mode:
            self.payment_difference_handling = previous_handling
        if batch_result.get("lines"):
            payment_vals["payment_has_invoice_lines"] = True
        return self._apply_advance_account_to_writeoff_lines(payment_vals)

    def _create_payment_vals_from_batch(self, batch_result):
        payment_vals = super()._create_payment_vals_from_batch(batch_result)
        if batch_result.get("lines"):
            payment_vals["payment_has_invoice_lines"] = True
        return self._apply_advance_account_to_writeoff_lines(payment_vals)

    @api.onchange(
        "amount",
        "payment_difference",
        "payment_difference_handling",
        "payment_difference_handling_overpay",
        "partner_id",
        "partner_type",
        "payment_type",
        "writeoff_is_exchange_account",
        "early_payment_discount_mode",
    )
    def _onchange_payment_difference_advance_account(self):
        if self._should_use_advance_for_payment_difference():
            self._prepare_advance_writeoff_defaults()

    @api.onchange("l10n_ve_apply_advance", "l10n_ve_advance_line_id", "line_ids")
    def _onchange_l10n_ve_apply_advance_amount(self):
        if not self.l10n_ve_apply_advance or not self.l10n_ve_advance_line_id:
            return
        max_amount = min(
            self.l10n_ve_advance_amount_available,
            self.l10n_ve_invoice_amount_residual,
        )
        if not self.currency_id.is_zero(max_amount):
            self.amount = max_amount

    def _create_payments(self):
        payments = super()._create_payments()
        payments.filtered(
            "l10n_ve_is_advance_application"
        )._l10n_ve_reconcile_advance_source_lines()
        return payments
