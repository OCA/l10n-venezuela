import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

CUSTOMER_INVOICE_TYPES = ("out_invoice", "out_refund")


class AccountPaymentRegister(models.TransientModel):
    _inherit = "account.payment.register"

    l10n_ve_apply_igtf = fields.Boolean(
        string="Apply IGTF",
        compute="_compute_l10n_ve_apply_igtf",
        store=True,
    )
    l10n_ve_igtf_included = fields.Boolean(
        string="Include IGTF in amount",
        default=False,
        help="If enabled, the suggested amount includes IGTF (residual + IGTF).",
    )
    l10n_ve_igtf_currency_ids = fields.Many2many(
        related="company_id.l10n_ve_igtf_currency_ids",
        readonly=True,
    )
    l10n_ve_igtf_feature_active = fields.Boolean(
        related="company_id.l10n_ve_igtf_feature_active",
        readonly=True,
    )
    l10n_ve_show_apply_igtf = fields.Boolean(
        string="Show Apply IGTF",
        compute="_compute_l10n_ve_show_apply_igtf",
        store=False,
    )
    l10n_ve_base_amount_company_currency = fields.Monetary(
        string="Base amount (Company currency)",
        currency_field="company_currency_id",
        compute="_compute_l10n_ve_base_amount_company_currency",
        store=False,
        readonly=True,
        help="Amount to which IGTF is applied, expressed in the company currency.",
    )
    l10n_ve_igtf_amount_company_currency = fields.Monetary(
        string="IGTF (Company currency)",
        currency_field="company_currency_id",
        compute="_compute_l10n_ve_igtf_amount_company_currency",
        store=False,
        readonly=True,
        help="Computed IGTF amount expressed in the company currency.",
    )
    l10n_ve_igtf_amount_currency = fields.Monetary(
        string="IGTF (Payment currency)",
        currency_field="currency_id",
        compute="_compute_l10n_ve_igtf_amount_currency",
        store=False,
        readonly=True,
        help="Computed IGTF amount expressed in the payment currency.",
    )
    l10n_ve_igtf_limit_reached = fields.Boolean(
        string="IGTF limit reached",
        compute="_compute_l10n_ve_igtf_limit_reached",
        store=False,
    )
    l10n_ve_igtf_limit_explanation = fields.Html(
        string="IGTF limit explanation",
        compute="_compute_l10n_ve_igtf_limit_reached",
        store=False,
    )
    l10n_ve_igtf_exceeds_max = fields.Boolean(
        string="IGTF exceeds maximum",
        compute="_compute_l10n_ve_igtf_exceeds_max",
        store=False,
    )
    l10n_ve_igtf_exceeds_max_explanation = fields.Html(
        string="IGTF exceeds max explanation",
        compute="_compute_l10n_ve_igtf_exceeds_max",
        store=False,
    )
    l10n_ve_igtf_exchange_rate_inverse = fields.Float(
        string="Exchange rate",
        compute="_compute_l10n_ve_igtf_exchange_rate_inverse",
        store=False,
        readonly=True,
        digits=(12, 6),
        help="1 unit of payment currency = X units of company currency.",
    )
    l10n_ve_ves_show_bolivar_split = fields.Boolean(
        compute="_compute_l10n_ve_ves_suggested_bolivar_split",
        store=False,
    )
    l10n_ve_ves_suggested_base = fields.Monetary(
        string="Límite abono Bs (excl. IGTF en saldo)",
        currency_field="company_currency_id",
        compute="_compute_l10n_ve_ves_suggested_bolivar_split",
        store=False,
        readonly=True,
    )
    l10n_ve_ves_suggested_igtf = fields.Monetary(
        string="Límite abono Bs (parte IGTF del saldo)",
        currency_field="company_currency_id",
        compute="_compute_l10n_ve_ves_suggested_bolivar_split",
        store=False,
        readonly=True,
    )
    l10n_ve_ves_payment_cap = fields.Monetary(
        string="Tope de pago de Bs",
        currency_field="company_currency_id",
        compute="_compute_l10n_ve_ves_suggested_bolivar_split",
        store=False,
        readonly=True,
    )

    def _l10n_ve_is_venezuela_company(self):
        self.ensure_one()
        if (
            not self.company_id.account_fiscal_country_id
            or self.company_id.account_fiscal_country_id.code != "VE"
        ):
            return False
        return self.company_id._l10n_ve_igtf_is_active()

    def _l10n_ve_get_igtf_percent(self):
        self.ensure_one()
        return self.company_id.l10n_ve_igtf_percent or 0.0

    def _l10n_ve_get_igtf_rate(self):
        self.ensure_one()
        percent = self._l10n_ve_get_igtf_percent()
        return percent / 100.0 if percent else 0.0

    def _l10n_ve_get_allowed_currencies(self):
        self.ensure_one()
        return self.company_id.l10n_ve_igtf_currency_ids

    def _l10n_ve_currency_applies_igtf(self):
        self.ensure_one()
        return (
            self.currency_id
            and self.currency_id in self._l10n_ve_get_allowed_currencies()
        )

    def _get_lines(self):
        if not self.batches:
            return self.env["account.move.line"]
        return self.batches[0]["lines"]

    def _l10n_ve_get_residual_in_payment_currency(self):
        self.ensure_one()
        residual = self.source_amount_currency
        if (
            self.source_currency_id
            and self.currency_id
            and self.source_currency_id != self.currency_id
        ):
            residual = self.source_currency_id._convert(
                self.source_amount_currency,
                self.currency_id,
                self.company_id,
                self.payment_date,
            )
        return residual

    def _l10n_ve_get_igtf_base_from_amount(self, amount, igtf_included):
        self.ensure_one()
        rate = self._l10n_ve_get_igtf_rate()
        if igtf_included:
            return amount / (1.0 + rate)
        return amount

    def _l10n_ve_get_capped_base(self, base_from_amount, residual):
        if residual:
            return min(base_from_amount, residual)
        return base_from_amount

    def _l10n_ve_will_use_force_balance(self):
        self.ensure_one()
        return (
            self.currency_id != self.company_currency_id
            and self.payment_difference_handling == "reconcile"
            and not self.currency_id.is_zero(self.payment_difference)
            and self.writeoff_is_exchange_account
        )

    @api.depends(
        "can_edit_wizard",
        "source_amount",
        "source_amount_currency",
        "source_currency_id",
        "company_id",
        "company_id.l10n_ve_igtf_feature_active",
        "currency_id",
        "payment_date",
        "installments_mode",
        "batches",
    )
    def _compute_amount(self):
        result = super()._compute_amount()
        for wiz in self:
            if not wiz.journal_id or not wiz.currency_id or not wiz.payment_date:
                continue
            if wiz.custom_user_amount:
                continue
            if not wiz._l10n_ve_is_venezuela_company():
                continue
            cap = wiz._l10n_ve_get_max_ves_payment_full_residual_in_company_currency()
            if cap is None:
                continue
            if wiz.currency_id.compare_amounts(wiz.amount, cap) > 0:
                wiz.amount = cap
        return result

    def _l10n_ve_wizard_pays_full_residual(self):
        self.ensure_one()
        if not self.batches or not self.currency_id:
            return False
        totals = self._get_total_amounts_to_pay(self.batches)
        return self.currency_id.compare_amounts(self.amount, totals["full_amount"]) == 0

    @api.depends(
        "early_payment_discount_mode",
        "can_edit_wizard",
        "currency_id",
        "company_currency_id",
        "payment_difference",
        "l10n_ve_apply_igtf",
        "amount",
        "batches",
    )
    def _compute_payment_difference_handling(self):
        result = super()._compute_payment_difference_handling()
        for wizard in self:
            if not wizard.can_edit_wizard:
                continue
            if wizard.early_payment_discount_mode:
                continue
            if wizard.l10n_ve_apply_igtf:
                wizard.payment_difference_handling = "open"
                continue
            if (
                wizard._l10n_ve_is_venezuela_company()
                and wizard.currency_id
                and wizard.currency_id != wizard.company_currency_id
                and not wizard.currency_id.is_zero(wizard.payment_difference)
                and wizard._l10n_ve_wizard_pays_full_residual()
            ):
                wizard.payment_difference_handling = "reconcile"
        return result

    @api.depends(
        "can_edit_wizard",
        "amount",
        "installments_mode",
        "l10n_ve_apply_igtf",
        "l10n_ve_igtf_included",
        "l10n_ve_igtf_amount_currency",
    )
    def _compute_payment_difference(self):
        result = super()._compute_payment_difference()
        for wizard in self:
            if (
                wizard.payment_date
                and wizard.l10n_ve_apply_igtf
                and wizard.l10n_ve_igtf_included
                and wizard.currency_id
            ):
                wizard.payment_difference += wizard.l10n_ve_igtf_amount_currency
        return result

    def _l10n_ve_get_invoice_total_in_company_currency(self, move):
        self.ensure_one()
        return abs(
            move.currency_id._convert(
                move.amount_total,
                self.company_currency_id,
                self.company_id,
                move.date,
            )
        )

    def _l10n_ve_get_customer_moves_from_lines(self, lines):
        return lines.move_id.filtered(lambda m: m.move_type in CUSTOMER_INVOICE_TYPES)

    def _l10n_ve_get_igtf_residual_company_amount(self, lines=None):
        if lines is None:
            self.ensure_one()
            lines = self._get_lines()
        moves = self._l10n_ve_get_customer_moves_from_lines(lines)
        if not moves:
            return None
        residual_total = 0.0
        for move in moves:
            residual_total += move._l10n_ve_igtf_get_residual_company_amount()
        return self.company_currency_id.round(max(residual_total, 0.0))

    def _l10n_ve_get_igtf_limit_status(self, lines=None):
        if lines is None:
            self.ensure_one()
            lines = self._get_lines()

        if not lines:
            return False, ""

        if not self._l10n_ve_is_venezuela_company():
            return False, ""

        percent = self._l10n_ve_get_igtf_percent()
        if percent <= 0.0:
            return False, ""

        moves = self._l10n_ve_get_customer_moves_from_lines(lines)
        if not moves:
            return False, ""

        rate = percent / 100.0
        max_igtf = 0.0
        igtf_already_collected = 0.0

        for move in moves:
            inv_total = self._l10n_ve_get_invoice_total_in_company_currency(move)
            max_igtf += self.company_currency_id.round(inv_total * rate)
            _collected_currency, already = move._l10n_ve_igtf_get_collected_amounts()
            igtf_already_collected += already

        igtf_already_collected = self.company_currency_id.round(igtf_already_collected)

        if igtf_already_collected >= max_igtf:
            message = _(
                "No se puede aplicar IGTF porque el monto máximo de "
                "IGTF permitido "
                "(%(max)s %(currency)s, equivalente al %(pct)s%% del "
                "total de la factura en moneda del sistema) "
                "ya fue cobrado en pagos anteriores "
                "(%(already)s %(currency)s)."
            ) % {
                "max": max_igtf,
                "already": igtf_already_collected,
                "pct": percent,
                "currency": self.company_currency_id.symbol
                or self.company_currency_id.name,
            }
            return True, message

        return False, ""

    def _l10n_ve_get_igtf_exceeds_max_status(self):
        self.ensure_one()
        if not self._l10n_ve_is_venezuela_company() or not self.l10n_ve_apply_igtf:
            return False, ""

        percent = self._l10n_ve_get_igtf_percent()
        if percent <= 0.0 or not self.batches:
            return False, ""

        currency_symbol = (
            self.company_currency_id.symbol or self.company_currency_id.name
        )

        if self.can_edit_wizard:
            first_batch = self.batches[0]
            is_single = len(first_batch["lines"]) == 1 or self.group_payment
            if is_single:
                max_igtf, igtf_already, igtf_this_currency = (
                    self._l10n_ve_compute_igtf_for_moves(
                        self._l10n_ve_get_customer_moves_from_lines(
                            first_batch.get("lines", self.env["account.move.line"])
                        ),
                        self.l10n_ve_igtf_included,
                        self.amount,
                    )
                )
                igtf_this_company = self.company_currency_id.round(
                    self.currency_id._convert(
                        igtf_this_currency,
                        self.company_currency_id,
                        self.company_id,
                        self.payment_date,
                    )
                )
                max_available = max_igtf - igtf_already
                if igtf_this_company > max_available:
                    return True, _(
                        "El IGTF calculado (%(this)s %(currency)s) "
                        "supera el máximo permitido "
                        "(%(max)s %(currency)s, equivalente al "
                        "%(pct)s%% del total de la factura en moneda "
                        "del sistema). "
                        "Ya se cobró %(already)s %(currency)s en "
                        "pagos anteriores."
                    ) % {
                        "this": igtf_this_company,
                        "max": max_igtf,
                        "already": igtf_already,
                        "pct": percent,
                        "currency": currency_symbol,
                    }
                return False, ""

        for batch in self.batches:
            lines = batch.get("lines", self.env["account.move.line"])
            moves = self._l10n_ve_get_customer_moves_from_lines(lines)
            if not moves:
                continue
            total_vals = self._get_total_amounts_to_pay([batch])
            amount = total_vals.get("amount_by_default", 0.0)
            max_igtf, igtf_already, igtf_this_currency = (
                self._l10n_ve_compute_igtf_for_moves(
                    moves, self.l10n_ve_igtf_included, amount
                )
            )
            igtf_this_company = self.company_currency_id.round(
                self.currency_id._convert(
                    igtf_this_currency,
                    self.company_currency_id,
                    self.company_id,
                    self.payment_date,
                )
            )
            max_available = max_igtf - igtf_already
            if igtf_this_company > max_available:
                return True, _(
                    "El IGTF calculado (%(this)s %(currency)s) "
                    "supera el máximo permitido "
                    "(%(max)s %(currency)s, equivalente al "
                    "%(pct)s%% del total de la factura en moneda "
                    "del sistema). "
                    "Ya se cobró %(already)s %(currency)s en "
                    "pagos anteriores."
                ) % {
                    "this": igtf_this_company,
                    "max": max_igtf,
                    "already": igtf_already,
                    "pct": percent,
                    "currency": currency_symbol,
                }

        return False, ""

    def _l10n_ve_compute_igtf_for_moves(self, moves, igtf_included, amount):
        self.ensure_one()
        percent = self._l10n_ve_get_igtf_percent()
        rate = percent / 100.0

        max_igtf = 0.0
        igtf_already = 0.0

        for move in moves:
            inv_total = self._l10n_ve_get_invoice_total_in_company_currency(move)
            max_igtf += self.company_currency_id.round(inv_total * rate)
            _collected_currency, already = move._l10n_ve_igtf_get_collected_amounts()
            igtf_already += already

        igtf_already = self.company_currency_id.round(igtf_already)

        if igtf_included:
            igtf_this = amount * rate / (1.0 + rate)
        else:
            igtf_this = amount * rate

        return max_igtf, igtf_already, igtf_this

    def _l10n_ve_validate_igtf_does_not_exceed_limit(
        self, batch_result, amount, apply_igtf, igtf_included
    ):
        self.ensure_one()
        if not self._l10n_ve_is_venezuela_company() or not apply_igtf:
            return

        percent = self._l10n_ve_get_igtf_percent()
        if percent <= 0.0:
            return

        lines = batch_result.get("lines", self.env["account.move.line"])
        if not lines:
            return

        moves = self._l10n_ve_get_customer_moves_from_lines(lines)
        if not moves:
            return

        max_igtf, igtf_already, igtf_this_currency = (
            self._l10n_ve_compute_igtf_for_moves(moves, igtf_included, amount)
        )

        igtf_this_company = self.currency_id._convert(
            igtf_this_currency,
            self.company_currency_id,
            self.company_id,
            self.payment_date,
        )
        igtf_this_company = self.company_currency_id.round(igtf_this_company)
        total_igtf = igtf_already + igtf_this_company

        if total_igtf > max_igtf:
            _logger.info(
                "IGTF exceeds limit in payment register; it will "
                "be capped on payment line creation."
            )

    def _l10n_ve_get_igtf_cap_company_for_batch(self, batch_result):
        lines = batch_result.get("lines", self.env["account.move.line"])
        if not lines:
            return 0.0
        moves = self._l10n_ve_get_customer_moves_from_lines(lines)
        if not moves:
            return 0.0
        residual_total = 0.0
        for move in moves:
            residual_total += move._l10n_ve_igtf_get_residual_company_amount()
        return self.company_currency_id.round(max(residual_total, 0.0))

    def _l10n_ve_get_max_ves_payment_wo_igtf(self):
        self.ensure_one()
        if not self._l10n_ve_is_venezuela_company():
            return None
        if not self.currency_id or self.currency_id != self.company_currency_id:
            return None
        if not self.batches or not self.payment_date:
            return None
        lines = self._get_lines()
        moves = self._l10n_ve_get_customer_moves_from_lines(lines)
        if not any(m.l10n_ve_igtf_invoice_has_igtf_accrual() for m in moves):
            return None
        total = 0.0
        for move in moves:
            if not move.l10n_ve_igtf_invoice_has_igtf_accrual():
                res_wo = (
                    move.l10n_ve_igtf_get_residual_excluding_igtf_in_document_currency()
                )
            else:
                ceiling = move.l10n_ve_igtf_get_wo_igtf_total_in_document_currency()
                used_bs = (
                    move.l10n_ve_igtf_get_cumulative_bs_paid_in_document_currency()
                )
                res_wo = (
                    move.l10n_ve_igtf_get_residual_excluding_igtf_in_document_currency()
                )
                left_from_ceiling = max(ceiling - used_bs, 0.0)
                res_wo = min(res_wo, left_from_ceiling)
            if move.currency_id.is_zero(res_wo):
                continue
            total += move.currency_id._convert(
                res_wo,
                self.currency_id,
                self.company_id,
                self.payment_date,
            )
        return self.currency_id.round(total)

    def _l10n_ve_get_max_ves_payment_full_residual_in_company_currency(self):
        return self._l10n_ve_get_ves_payment_cap_company_currency()

    def _l10n_ve_get_ves_payment_cap_company_currency(self):
        self.ensure_one()
        if not self._l10n_ve_is_venezuela_company():
            return None
        if not self.currency_id or self.currency_id != self.company_currency_id:
            return None
        if not self.batches or not self.payment_date:
            return None
        lines = self._get_lines()
        moves = self._l10n_ve_get_customer_moves_from_lines(lines)
        if not any(m.l10n_ve_igtf_invoice_has_igtf_accrual() for m in moves):
            return None
        total = 0.0
        for move in moves:
            base_doc = (
                move.l10n_ve_igtf_get_residual_excluding_igtf_in_document_currency()
            )
            ceiling = move.l10n_ve_igtf_get_wo_igtf_total_in_document_currency()
            used_bs = move.l10n_ve_igtf_get_cumulative_bs_paid_in_document_currency()
            base_left_from_ceiling = max(ceiling - used_bs, 0.0)
            base_doc = min(base_doc, base_left_from_ceiling)
            igtf_doc = (
                move.l10n_ve_igtf_get_bs_payable_igtf_residual_in_document_currency()
            )
            res_doc = move.currency_id.round(base_doc + igtf_doc)
            if move.currency_id.is_zero(res_doc):
                continue
            total += move.currency_id._convert(
                res_doc,
                self.currency_id,
                self.company_id,
                self.payment_date,
            )
        return self.currency_id.round(total)

    def _l10n_ve_batches_contain_only_customer_invoices(self):
        self.ensure_one()
        if not self.batches:
            return True
        for batch in self.batches:
            lines = batch.get("lines", self.env["account.move.line"])
            if lines:
                moves = lines.move_id
                if moves and any(
                    m.move_type not in CUSTOMER_INVOICE_TYPES for m in moves
                ):
                    return False
        return True

    @api.depends(
        "company_id",
        "company_id.l10n_ve_igtf_percent",
        "company_id.l10n_ve_igtf_feature_active",
        "currency_id",
        "l10n_ve_igtf_limit_reached",
        "amount",
        "batches",
    )
    def _compute_l10n_ve_apply_igtf(self):
        for record in self:
            if not record._l10n_ve_is_venezuela_company():
                record.l10n_ve_apply_igtf = False
                continue

            if not record._l10n_ve_get_igtf_percent():
                record.l10n_ve_apply_igtf = False
                continue

            if not record._l10n_ve_currency_applies_igtf():
                record.l10n_ve_apply_igtf = False
                continue

            if record.l10n_ve_igtf_limit_reached:
                record.l10n_ve_apply_igtf = False
                continue

            if record._l10n_ve_invoices_in_wizard_have_igtf_on_move():
                record.l10n_ve_apply_igtf = False
                continue

            record.l10n_ve_apply_igtf = True

    def _l10n_ve_invoices_in_wizard_have_igtf_on_move(self):
        for batch in self.batches or []:
            for line in batch.get("lines", self.env["account.move.line"]):
                if line.move_id.l10n_ve_igtf_invoice_has_igtf_accrual():
                    return True
        return False

    @api.depends(
        "batches",
        "company_id",
        "company_id.l10n_ve_igtf_percent",
        "company_id.l10n_ve_igtf_feature_active",
    )
    def _compute_l10n_ve_igtf_limit_reached(self):
        for wiz in self:
            limit_reached, explanation = wiz._l10n_ve_get_igtf_limit_status()
            wiz.l10n_ve_igtf_limit_reached = limit_reached
            wiz.l10n_ve_igtf_limit_explanation = explanation

    @api.depends(
        "l10n_ve_apply_igtf",
        "l10n_ve_igtf_included",
        "amount",
        "currency_id",
        "payment_date",
        "batches",
        "company_id",
        "company_id.l10n_ve_igtf_percent",
        "company_id.l10n_ve_igtf_feature_active",
        "group_payment",
        "can_edit_wizard",
    )
    def _compute_l10n_ve_igtf_exceeds_max(self):
        for wiz in self:
            exceeds, explanation = wiz._l10n_ve_get_igtf_exceeds_max_status()
            wiz.l10n_ve_igtf_exceeds_max = exceeds
            wiz.l10n_ve_igtf_exceeds_max_explanation = explanation

    @api.onchange(
        "batches",
        "company_id",
        "l10n_ve_igtf_limit_reached",
    )
    def _onchange_l10n_ve_igtf_limit_reached(self):
        if self.l10n_ve_igtf_limit_reached and self.l10n_ve_apply_igtf:
            self.l10n_ve_apply_igtf = False

    @api.depends(
        "currency_id",
        "company_id",
        "company_id.l10n_ve_igtf_currency_ids",
        "company_id.l10n_ve_igtf_feature_active",
        "batches",
    )
    def _compute_l10n_ve_show_apply_igtf(self):
        for wiz in self:
            if not wiz._l10n_ve_is_venezuela_company():
                wiz.l10n_ve_show_apply_igtf = False
                continue

            if not wiz._l10n_ve_batches_contain_only_customer_invoices():
                wiz.l10n_ve_show_apply_igtf = False
                continue

            if wiz._l10n_ve_invoices_in_wizard_have_igtf_on_move():
                wiz.l10n_ve_show_apply_igtf = False
                continue

            wiz.l10n_ve_show_apply_igtf = wiz._l10n_ve_currency_applies_igtf()

    @api.depends(
        "l10n_ve_apply_igtf",
        "l10n_ve_igtf_included",
        "amount",
        "currency_id",
        "payment_date",
        "source_amount_currency",
        "source_currency_id",
        "company_id",
        "company_currency_id",
        "company_id.l10n_ve_igtf_percent",
        "company_id.l10n_ve_igtf_feature_active",
    )
    def _compute_l10n_ve_igtf_amount_currency(self):
        for wiz in self:
            (
                _base_company,
                igtf_amount_currency,
                _igtf_amount_company,
            ) = wiz._l10n_ve_get_igtf_amounts_for_wizard()
            wiz.l10n_ve_igtf_amount_currency = igtf_amount_currency

    def _l10n_ve_get_igtf_amounts_for_wizard(self):
        self.ensure_one()
        if not self._l10n_ve_is_venezuela_company():
            return 0.0, 0.0, 0.0
        percent = self._l10n_ve_get_igtf_percent()
        if not self.l10n_ve_apply_igtf or percent <= 0.0 or not self.currency_id:
            return 0.0, 0.0, 0.0
        if not self._l10n_ve_currency_applies_igtf():
            return 0.0, 0.0, 0.0

        residual = self._l10n_ve_get_residual_in_payment_currency()
        base_from_amount = self._l10n_ve_get_igtf_base_from_amount(
            self.amount, self.l10n_ve_igtf_included
        )
        base_currency = self._l10n_ve_get_capped_base(base_from_amount, residual)
        rate = self._l10n_ve_get_igtf_rate()
        base_company = self.company_currency_id.round(
            self.currency_id._convert(
                base_currency,
                self.company_currency_id,
                self.company_id,
                self.payment_date,
            )
        )
        raw_igtf_company = self.company_currency_id.round(base_company * rate)
        cap_company = self._l10n_ve_get_igtf_residual_company_amount()
        igtf_company = (
            min(raw_igtf_company, cap_company)
            if cap_company is not None
            else raw_igtf_company
        )
        if self.company_currency_id.is_zero(igtf_company):
            return 0.0, 0.0, 0.0
        igtf_currency = self.currency_id.round(
            self.company_currency_id._convert(
                igtf_company,
                self.currency_id,
                self.company_id,
                self.payment_date,
            )
        )
        base_company = (
            self.company_currency_id.round(igtf_company / rate) if rate else 0.0
        )
        return base_company, igtf_currency, igtf_company

    def _l10n_ve_compute_igtf_amount_company_currency_for_base(self):
        self.ensure_one()
        rate = self._l10n_ve_get_igtf_rate()
        if self.l10n_ve_igtf_included:
            igtf_currency = self.amount * rate / (1.0 + rate)
        else:
            igtf_currency = self.amount * rate
        return self.company_currency_id.round(
            self.currency_id._convert(
                igtf_currency,
                self.company_currency_id,
                self.company_id,
                self.payment_date,
            )
        )

    @api.depends(
        "l10n_ve_apply_igtf",
        "l10n_ve_igtf_included",
        "amount",
        "currency_id",
        "payment_date",
        "source_amount",
        "source_amount_currency",
        "source_currency_id",
        "payment_difference",
        "payment_difference_handling",
        "writeoff_account_id",
        "company_id",
        "company_currency_id",
        "company_id.l10n_ve_igtf_percent",
        "company_id.l10n_ve_igtf_feature_active",
    )
    def _compute_l10n_ve_base_amount_company_currency(self):
        for wiz in self:
            (
                base_company,
                _igtf_amount_currency,
                _igtf_amount_company,
            ) = wiz._l10n_ve_get_igtf_amounts_for_wizard()
            wiz.l10n_ve_base_amount_company_currency = base_company

    @api.depends(
        "currency_id",
        "company_currency_id",
        "company_id",
        "company_id.l10n_ve_igtf_feature_active",
        "payment_date",
    )
    def _compute_l10n_ve_igtf_exchange_rate_inverse(self):
        for wiz in self:
            if not wiz._l10n_ve_is_venezuela_company():
                wiz.l10n_ve_igtf_exchange_rate_inverse = 1.0
                continue
            if (
                not wiz.currency_id
                or not wiz.company_currency_id
                or wiz.currency_id == wiz.company_currency_id
            ):
                wiz.l10n_ve_igtf_exchange_rate_inverse = 1.0
                continue
            rate = wiz.currency_id._convert(
                1.0,
                wiz.company_currency_id,
                wiz.company_id,
                wiz.payment_date,
                round=False,
            )
            wiz.l10n_ve_igtf_exchange_rate_inverse = rate or 0.0

    @api.depends(
        "batches",
        "currency_id",
        "company_currency_id",
        "payment_date",
        "can_edit_wizard",
        "company_id",
        "company_id.l10n_ve_igtf_feature_active",
    )
    def _compute_l10n_ve_ves_suggested_bolivar_split(self):
        for wiz in self:
            if not wiz._l10n_ve_is_venezuela_company():
                wiz.l10n_ve_ves_show_bolivar_split = False
                wiz.l10n_ve_ves_suggested_base = 0.0
                wiz.l10n_ve_ves_suggested_igtf = 0.0
                wiz.l10n_ve_ves_payment_cap = 0.0
                continue
            cap_full = (
                wiz._l10n_ve_get_max_ves_payment_full_residual_in_company_currency()
            )
            if cap_full is None or not wiz.currency_id:
                wiz.l10n_ve_ves_show_bolivar_split = False
                wiz.l10n_ve_ves_suggested_base = 0.0
                wiz.l10n_ve_ves_suggested_igtf = 0.0
                wiz.l10n_ve_ves_payment_cap = 0.0
                continue
            base = wiz._l10n_ve_get_max_ves_payment_wo_igtf() or 0.0
            full = cap_full
            extra = max(wiz.currency_id.round(full - base), 0.0)
            wiz.l10n_ve_ves_show_bolivar_split = not wiz.currency_id.is_zero(
                cap_full
            ) and (
                not wiz.currency_id.is_zero(base) or not wiz.currency_id.is_zero(extra)
            )
            wiz.l10n_ve_ves_suggested_base = base
            wiz.l10n_ve_ves_suggested_igtf = extra
            wiz.l10n_ve_ves_payment_cap = full

    @api.depends(
        "l10n_ve_igtf_amount_currency",
        "currency_id",
        "company_currency_id",
        "company_id",
        "company_id.l10n_ve_igtf_feature_active",
        "payment_date",
    )
    def _compute_l10n_ve_igtf_amount_company_currency(self):
        for wiz in self:
            (
                _base_company,
                _igtf_amount_currency,
                igtf_amount_company,
            ) = wiz._l10n_ve_get_igtf_amounts_for_wizard()
            wiz.l10n_ve_igtf_amount_company_currency = igtf_amount_company

    @api.onchange(
        "amount",
        "payment_difference_handling",
        "currency_id",
        "journal_id",
    )
    def _onchange_l10n_ve_default_exchange_writeoff_account(self):
        if not self._l10n_ve_is_venezuela_company():
            return
        if self.l10n_ve_apply_igtf:
            self.writeoff_account_id = False
            return
        if not self.currency_id or self.currency_id == self.company_currency_id:
            return
        if not self.batches:
            return
        try:
            total_amount_values = self._get_total_amounts_to_pay(self.batches)
            amount_for_diff = total_amount_values.get("amount_for_difference", 0)
            payment_diff = amount_for_diff - self.amount if self.amount else 0
        except Exception:
            return
        if self.currency_id.is_zero(payment_diff):
            return
        exchange_account = (
            self.company_id.income_currency_exchange_account_id
            if self.payment_type == "inbound"
            else self.company_id.expense_currency_exchange_account_id
        )
        if exchange_account and self.writeoff_account_id != exchange_account:
            self.writeoff_account_id = exchange_account

    @api.onchange(
        "l10n_ve_apply_igtf",
        "l10n_ve_igtf_included",
        "currency_id",
        "payment_date",
    )
    def _onchange_l10n_ve_igtf_included(self):
        for wiz in self:
            if not wiz.can_edit_wizard:
                continue

            if not wiz.l10n_ve_apply_igtf:
                wiz.l10n_ve_igtf_included = False
                continue

            if not wiz.l10n_ve_igtf_included:
                wiz.custom_user_amount = False
                wiz.custom_user_currency_id = False
                continue

            percent = wiz._l10n_ve_get_igtf_percent()
            if percent <= 0.0 or not wiz._l10n_ve_currency_applies_igtf():
                continue

            rate = wiz._l10n_ve_get_igtf_rate()
            total_amounts = (
                wiz._get_total_amounts_to_pay(wiz.batches) if wiz.batches else {}
            )
            base_amount = total_amounts.get("amount_by_default", wiz.amount)
            suggested = wiz.currency_id.round(base_amount * (1.0 + rate))
            wiz.custom_user_currency_id = wiz.currency_id
            wiz.custom_user_amount = suggested
            wiz.amount = suggested

    def _l10n_ve_get_max_amount_with_igtf(self):
        self.ensure_one()
        rate = self._l10n_ve_get_igtf_rate()
        residual = self._l10n_ve_get_residual_in_payment_currency()
        return self.currency_id.round(residual * (1.0 + rate))

    def _l10n_ve_validate_amount_does_not_exceed_max(self):
        self.ensure_one()
        if not self._l10n_ve_is_venezuela_company():
            return

        if (
            not self.l10n_ve_apply_igtf
            or not self.currency_id
            or not self.payment_date
            or not self._l10n_ve_currency_applies_igtf()
        ):
            return

        # Overpayments are allowed; IGTF is capped later using residual IGTF available.
        return

    @api.onchange(
        "amount",
        "batches",
        "payment_date",
        "currency_id",
    )
    def _onchange_l10n_ve_ves_cap_without_igtf(self):
        for wiz in self:
            if not wiz.can_edit_wizard or not wiz.currency_id or not wiz.payment_date:
                continue
            cap = wiz._l10n_ve_get_max_ves_payment_full_residual_in_company_currency()
            if cap is None or not wiz.amount:
                continue
            if wiz.currency_id.compare_amounts(wiz.amount, cap) > 0:
                wiz.amount = cap
                wiz.custom_user_amount = False
                wiz.custom_user_currency_id = False

    @api.onchange("amount", "l10n_ve_apply_igtf", "currency_id", "payment_date")
    def _onchange_l10n_ve_validate_amount_max_with_igtf(self):
        for wiz in self:
            if wiz.amount:
                wiz._l10n_ve_validate_amount_does_not_exceed_max()
            if (
                wiz.amount
                and wiz._l10n_ve_is_venezuela_company()
                and wiz.l10n_ve_apply_igtf
                and wiz.currency_id
                and wiz._l10n_ve_currency_applies_igtf()
            ):
                max_amount_with_igtf = wiz._l10n_ve_get_max_amount_with_igtf()
                if max_amount_with_igtf and wiz.amount > max_amount_with_igtf:
                    wiz.l10n_ve_igtf_included = True

    def _l10n_ve_check_register_payment_allowed_for_moves(self):
        self.ensure_one()
        if not self._l10n_ve_is_venezuela_company() or not self.batches:
            return
        if not self.currency_id or self.currency_id != self.company_currency_id:
            return
        lines = self._get_lines()
        moves = self._l10n_ve_get_customer_moves_from_lines(lines)
        for move in moves:
            if not move.l10n_ve_igtf_invoice_has_igtf_accrual():
                continue
            if not move.l10n_ve_igtf_hide_register_payment:
                continue
            raise UserError(
                _(
                    "No puede confirmar un pago en bolívares en el "
                    "estado actual de la factura "
                    "%(name)s: el asistente o las reglas de "
                    "cupo/IGTF no lo permiten. Compruebe el "
                    "abono o utilice otra moneda, o abra una nota "
                    "de crédito si corresponde a la "
                    "diferencia en moneda de la factura."
                )
                % {"name": (move.name or str(move.id))}
            )

    def _create_payments(self):
        self.ensure_one()

        if (
            self.l10n_ve_show_apply_igtf
            and not self.l10n_ve_apply_igtf
            and not self.l10n_ve_igtf_limit_reached
            and not self._l10n_ve_invoices_in_wizard_have_igtf_on_move()
        ):
            raise UserError(
                _(
                    "El IGTF es obligatorio cuando el pago es en "
                    "las monedas configuradas (ej. USD). "
                    "Debe aplicar IGTF para continuar."
                )
            )

        self._l10n_ve_check_register_payment_allowed_for_moves()

        max_bs = self._l10n_ve_get_max_ves_payment_full_residual_in_company_currency()
        if (
            max_bs is not None
            and self.currency_id.compare_amounts(self.amount, max_bs) > 0
        ):
            raise UserError(
                _(
                    "En bolívares el abono no puede ser mayor al "
                    "saldo pendiente total (incluye "
                    "el importe que corresponde a la base en moneda "
                    "documento e IGTF). Máximo "
                    "permitido ahora: %(max)s %(cur)s."
                )
                % {
                    "max": max_bs,
                    "cur": self.company_currency_id.symbol
                    or self.company_currency_id.name,
                }
            )

        self._l10n_ve_validate_amount_does_not_exceed_max()

        batches = [
            batch
            for batch in self.batches
            if not (
                self.require_partner_bank_account
                and (
                    not self._get_batch_account(batch)
                    or not self._get_batch_account(batch).allow_out_payment
                )
            )
        ]

        if batches:
            first_batch = batches[0]
            is_single_payment = self.can_edit_wizard and (
                len(first_batch["lines"]) == 1 or self.group_payment
            )

            if is_single_payment:
                self._l10n_ve_validate_igtf_does_not_exceed_limit(
                    first_batch,
                    self.amount,
                    self.l10n_ve_apply_igtf,
                    self.l10n_ve_igtf_included,
                )
            else:
                for batch_result in batches:
                    total_vals = self._get_total_amounts_to_pay([batch_result])
                    amount = total_vals.get("amount_by_default", 0.0)
                    self._l10n_ve_validate_igtf_does_not_exceed_limit(
                        batch_result,
                        amount,
                        self.l10n_ve_apply_igtf,
                        self.l10n_ve_igtf_included,
                    )

        return super(
            AccountPaymentRegister,
            self.with_context(l10n_ve_igtf_from_register_payment=True),
        )._create_payments()

    def _create_payment_vals_from_wizard(self, batch_result):
        vals = super()._create_payment_vals_from_wizard(batch_result)
        vals["l10n_ve_apply_igtf"] = self.l10n_ve_apply_igtf
        vals["l10n_ve_igtf_included"] = self.l10n_ve_igtf_included
        vals["l10n_ve_igtf_cap_amount_company_currency"] = (
            self._l10n_ve_get_igtf_cap_company_for_batch(batch_result)
        )
        if vals.get("l10n_ve_apply_igtf"):
            payment_method_line = self.env["account.payment.method.line"].browse(
                vals.get("payment_method_line_id")
            )
            journal = self.env["account.journal"].browse(vals.get("journal_id"))
            if (
                payment_method_line
                and journal
                and not payment_method_line.payment_account_id
                and journal.default_account_id
            ):
                vals["outstanding_account_id"] = journal.default_account_id.id
        return vals

    def _create_payment_vals_from_batch(self, batch_result):
        vals = super()._create_payment_vals_from_batch(batch_result)
        vals["l10n_ve_apply_igtf"] = self.l10n_ve_apply_igtf
        vals["l10n_ve_igtf_included"] = self.l10n_ve_igtf_included
        vals["l10n_ve_igtf_cap_amount_company_currency"] = (
            self._l10n_ve_get_igtf_cap_company_for_batch(batch_result)
        )
        if vals.get("l10n_ve_apply_igtf"):
            payment_method_line = self.env["account.payment.method.line"].browse(
                vals.get("payment_method_line_id")
            )
            journal = self.env["account.journal"].browse(vals.get("journal_id"))
            if (
                payment_method_line
                and journal
                and not payment_method_line.payment_account_id
                and journal.default_account_id
            ):
                vals["outstanding_account_id"] = journal.default_account_id.id
        return vals
