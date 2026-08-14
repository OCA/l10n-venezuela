import logging

from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_compare
from odoo.tools.misc import formatLang

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"

    l10n_ve_igtf_feature_active = fields.Boolean(
        related="company_id.l10n_ve_igtf_feature_active",
    )

    def _l10n_ve_igtf_aml(self):
        self.ensure_one()
        return self.line_ids.filtered(
            lambda line: line.display_type == "l10n_ve_igtf"
        )

    def _l10n_ve_igtf_move_applies(self):
        self.ensure_one()
        return (
            self.country_code == "VE"
            and self.company_id.l10n_ve_igtf_feature_active
        )

    @api.depends(
        "line_ids.matched_debit_ids.debit_move_id.move_id.origin_payment_id.is_matched",
        "line_ids.matched_debit_ids.debit_move_id.move_id.line_ids.amount_residual",
        "line_ids.matched_debit_ids.debit_move_id.move_id.line_ids.amount_residual_currency",
        "line_ids.matched_credit_ids.credit_move_id.move_id.origin_payment_id.is_matched",
        "line_ids.matched_credit_ids.credit_move_id.move_id.line_ids.amount_residual",
        "line_ids.matched_credit_ids.credit_move_id.move_id.line_ids.amount_residual_currency",
        "line_ids.balance",
        "line_ids.currency_id",
        "line_ids.amount_currency",
        "line_ids.amount_residual",
        "line_ids.amount_residual_currency",
        "line_ids.payment_id.state",
        "line_ids.full_reconcile_id",
        "line_ids.display_type",
        "state",
        "company_id.l10n_ve_igtf_feature_active",
        "company_id.l10n_ve_igtf_allow_invoice_accrual",
    )
    def _compute_amount(self):
        super()._compute_amount()
        for move in self:
            if not move.is_invoice(include_receipts=True):
                continue
            if not move._l10n_ve_igtf_move_applies():
                continue
            igtf_lines = move._l10n_ve_igtf_aml()
            if not igtf_lines:
                continue
            d_cur = sum(igtf_lines.mapped("amount_currency"))
            d_bal = sum(igtf_lines.mapped("balance"))
            if move.currency_id.is_zero(d_cur) and move.company_currency_id.is_zero(
                d_bal
            ):
                continue
            if _logger.isEnabledFor(logging.INFO):
                _logger.info(
                    "l10n_ve_igtf _compute_amount: move=%s d_cur=%s d_bal=%s -> amount_total+=%s",
                    move.id,
                    d_cur,
                    d_bal,
                    -d_cur,
                )
            move.amount_total -= d_cur
            move.amount_tax -= d_cur
            if move.move_type != "entry":
                move.amount_total_signed = move.amount_total_signed - d_bal
            move.amount_tax_signed = move.amount_tax_signed - d_bal

    l10n_ve_igtf_collected_amount_currency = fields.Monetary(
        string="IGTF %",
        currency_field="currency_id",
        compute="_compute_l10n_ve_igtf_collected_amounts",
        store=False,
        readonly=True,
    )
    l10n_ve_igtf_collected_amount_company_currency = fields.Monetary(
        string="IGTF % (Company Currency)",
        currency_field="company_currency_id",
        compute="_compute_l10n_ve_igtf_collected_amounts",
        store=False,
        readonly=True,
    )
    l10n_ve_igtf_residual_amount_company_currency = fields.Monetary(
        string="IGTF Residual (Company Currency)",
        currency_field="company_currency_id",
        compute="_compute_l10n_ve_igtf_collected_amounts",
        store=False,
        readonly=True,
    )
    l10n_ve_igtf_hide_register_payment = fields.Boolean(
        string="IGTF: ocultar Pagar en factura",
        compute="_compute_l10n_ve_igtf_hide_register_payment",
        help="Solo aplica en facturas con IGTF en VE: no mostrar Pagar si solo queda el IGTF o el cupo en Bs se agotó.",
    )
    l10n_ve_igtf_show_unpaid_in_doc_currency = fields.Boolean(
        compute="_compute_l10n_ve_igtf_show_unpaid_in_doc_currency",
        store=False,
    )
    l10n_ve_igtf_surplus_credit_note = fields.Boolean(
        string="Nota de crédito por IGTF sobrante",
        copy=False,
    )

    @api.depends(
        "state",
        "amount_residual",
        "currency_id",
        "move_type",
        "country_code",
        "company_id",
        "company_id.l10n_ve_igtf_feature_active",
        "company_id.l10n_ve_igtf_currency_ids",
        "company_id.l10n_ve_igtf_allow_invoice_accrual",
        "line_ids.display_type",
        "line_ids.amount_currency",
    )
    def _compute_l10n_ve_igtf_show_unpaid_in_doc_currency(self):
        for move in self:
            cur = move.currency_id
            base_residual = (
                move.l10n_ve_igtf_get_residual_excluding_igtf_in_document_currency()
                if move.l10n_ve_igtf_invoice_has_igtf_accrual()
                else move.amount_residual
            )
            doc_ok = (
                bool(cur)
                and not cur.is_zero(move.amount_residual)
                and cur.is_zero(base_residual)
                and cur in move.company_id.l10n_ve_igtf_currency_ids
            )
            move.l10n_ve_igtf_show_unpaid_in_doc_currency = bool(
                move._l10n_ve_igtf_move_applies()
                and move.is_sale_document(include_receipts=True)
                and move.state == "posted"
                and doc_ok
            )

    def action_l10n_ve_igtf_credit_note_by_difference(self):
        self.ensure_one()
        if not self._l10n_ve_igtf_move_applies() or not self.is_invoice(
            include_receipts=True
        ):
            return False
        if not self.l10n_ve_igtf_invoice_has_igtf_accrual():
            return False
        if not self.currency_id.is_zero(
            self.l10n_ve_igtf_get_residual_excluding_igtf_in_document_currency()
        ):
            raise UserError(
                _(
                    "La nota de crédito por IGTF sobrante solo se puede crear cuando "
                    "no queda base pendiente en la moneda del documento."
                )
            )
        if not self.company_id.l10n_ve_igtf_account_id:
            raise UserError(_("Debe configurar la cuenta contable de IGTF."))
        amount = self.currency_id.round(abs(self.amount_residual))
        if self.currency_id.is_zero(amount):
            return False
        credit_note_currency = self.company_currency_id
        credit_note_amount = credit_note_currency.round(
            self.currency_id._convert(
                amount,
                credit_note_currency,
                self.company_id,
                self.invoice_date or self.date or fields.Date.context_today(self),
            )
        )
        move_model = self.env["account.move"].with_context(l10n_ve_igtf_skip_igtf=True)
        credit_note = move_model.create(
            {
                "move_type": "out_refund",
                "reversed_entry_id": self.id,
                "partner_id": self.partner_id.id,
                "journal_id": self.journal_id.id,
                "company_id": self.company_id.id,
                "currency_id": credit_note_currency.id,
                "invoice_date": fields.Date.context_today(self),
                "date": fields.Date.context_today(self),
                "invoice_origin": self.name,
                "ref": _("IGTF sobrante de %s") % (self.name or ""),
                "l10n_ve_igtf_surplus_credit_note": True,
                "invoice_line_ids": [
                    Command.create(
                        {
                            "name": _("IGTF sobrante"),
                            "quantity": 1.0,
                            "price_unit": credit_note_amount,
                            "account_id": self.company_id.l10n_ve_igtf_account_id.id,
                            "tax_ids": [Command.clear()],
                        }
                    )
                ],
            }
        )
        return {
            "name": _("Nota de crédito por IGTF sobrante"),
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "view_mode": "form",
            "res_id": credit_note.id,
            "context": {"default_move_type": credit_note.move_type},
        }

    @api.depends(
        "state",
        "amount_residual",
        "amount_total",
        "country_code",
        "company_id.l10n_ve_igtf_feature_active",
        "company_id.l10n_ve_igtf_allow_invoice_accrual",
        "payment_state",
        "line_ids",
        "line_ids.display_type",
        "line_ids.matched_debit_ids",
        "line_ids.matched_credit_ids",
    )
    def _compute_l10n_ve_igtf_hide_register_payment(self):
        for move in self:
            h = False
            reason = "default"
            res_wo = 0.0
            ceiling = 0.0
            used_bs = 0.0
            n_partial = 0
            n_bs_partial = 0
            if not move._l10n_ve_igtf_move_applies() or not move.is_invoice(
                include_receipts=True
            ):
                h = False
                reason = "not_ve_or_not_invoice"
            elif not move.l10n_ve_igtf_invoice_has_igtf_accrual():
                h = False
                reason = "no_igtf_accrual"
            elif move.state != "posted":
                h = False
                reason = "not_posted"
            elif not move.currency_id or move.currency_id.is_zero(
                move.amount_residual
            ):
                h = True
                reason = "amount_residual_zero"
            else:
                res_wo = (
                    move.l10n_ve_igtf_get_residual_excluding_igtf_in_document_currency()
                )
                residual_igtf_payable_bs = (
                    move.l10n_ve_igtf_get_bs_payable_igtf_residual_in_document_currency()
                )
                if move.currency_id.is_zero(res_wo) and move.currency_id.is_zero(
                    residual_igtf_payable_bs
                ):
                    h = True
                    reason = "residual_wo_igtf_zero"
                else:
                    ceiling = move.l10n_ve_igtf_get_wo_igtf_total_in_document_currency()
                    (
                        used_bs,
                        n_partial,
                        n_bs_partial,
                    ) = move._l10n_ve_igtf_cumulative_bs_paid_in_document_currency_with_stats()
                    if not move.currency_id.is_zero(
                        ceiling
                    ) and move.currency_id.compare_amounts(used_bs, ceiling) >= 0:
                        h = True
                        reason = "cumulative_bs_ge_wo_igtf_total"
                    else:
                        h = False
                        reason = "residual_wo_igtf_and_bs_cupo_open"
            move.l10n_ve_igtf_hide_register_payment = h
            if _logger.isEnabledFor(logging.INFO) and reason not in {
                "not_ve_or_not_invoice",
                "no_igtf_accrual",
            }:
                has_igtf = move.l10n_ve_igtf_invoice_has_igtf_accrual()
                _logger.info(
                    "l10n_ve_igtf_hide_register_payment move=%s name=%s hide=%s reason=%s "
                    "state=%s pay_state=%s amount_residual=%s res_wo_igtf=%s "
                    "ceiling_wo_igtf=%s used_bs=%s n_partial_recon=%s n_bs_included=%s "
                    "currency=%s has_igtf=%s",
                    move.id,
                    (move.name or "-")[:64],
                    h,
                    reason,
                    move.state,
                    move.payment_state,
                    move.amount_residual,
                    res_wo,
                    ceiling,
                    used_bs,
                    n_partial,
                    n_bs_partial,
                    move.currency_id and move.currency_id.name,
                    has_igtf,
                )

    def _l10n_ve_igtf_get_document_base_total_in_currency(self):
        self.ensure_one()
        lines = self.invoice_line_ids.filtered(
            lambda line: line.display_type == "product" and line.price_total
        )
        if not lines:
            return 0.0
        return self.currency_id.round(
            sum(abs(line.price_total) for line in lines)
        )

    def _l10n_ve_igtf_should_add_move_lines(self):
        self.ensure_one()
        if self.l10n_ve_igtf_surplus_credit_note:
            return False
        if not self._l10n_ve_igtf_move_applies() or not self.is_sale_document(
            include_receipts=True
        ):
            return False
        if self.state != "draft":
            return False
        if not self.company_id.l10n_ve_igtf_allow_invoice_accrual:
            return False
        if not self.company_id.l10n_ve_igtf_account_id or not (
            self.company_id.l10n_ve_igtf_percent or 0.0
        ):
            return False
        if not self._l10n_ve_igtf_get_document_base_total_in_currency():
            return False
        if (
            self.move_type == "out_refund"
            and self.reversed_entry_id
            and self.currency_id == self.company_currency_id
            and self.reversed_entry_id._l10n_ve_igtf_origin_has_igtf()
        ):
            return True
        if not self.currency_id or self.currency_id not in self.company_id.l10n_ve_igtf_currency_ids:
            return False
        return True

    @api.depends(
        "invoice_payment_term_id",
        "invoice_date",
        "currency_id",
        "amount_total_in_currency_signed",
        "invoice_date_due",
        "line_ids.display_type",
        "line_ids.amount_currency",
    )
    def _compute_needed_terms(self):
        super()._compute_needed_terms()
        for move in self:
            if not move.l10n_ve_igtf_invoice_has_igtf_accrual():
                continue
            if not move.needed_terms or len(move.needed_terms) != 1:
                continue
            igtf_amount_currency = sum(move._l10n_ve_igtf_aml().mapped("amount_currency"))
            if move.currency_id.is_zero(igtf_amount_currency):
                continue
            key = next(iter(move.needed_terms))
            values = dict(move.needed_terms[key])
            values["amount_currency"] = move.currency_id.round(
                values["amount_currency"] - igtf_amount_currency
            )
            move.needed_terms = {key: values}

    def _l10n_ve_igtf_get_from_invoice_igtf_lines(self, include_base=False):
        self.ensure_one()
        sign = 1.0
        if self.move_type == "out_refund":
            sign = -1.0
        igtf_lines = self._l10n_ve_igtf_aml()
        doc_base = self._l10n_ve_igtf_get_document_base_total_in_currency()
        if not igtf_lines:
            if include_base:
                b = self.currency_id.round(sign * doc_base) if doc_base else 0.0
                bc = (
                    self.company_currency_id.round(
                        self.currency_id._convert(
                            b,
                            self.company_currency_id,
                            self.company_id,
                            self.date,
                        )
                    )
                    if doc_base
                    else 0.0
                )
                return b, bc, 0.0, 0.0
            return 0.0, 0.0
        igtf_currency = self.currency_id.round(sum(igtf_lines.mapped("amount_currency")))
        igtf_company = self.company_currency_id.round(
            sum(igtf_lines.mapped("balance"))
        )
        base_s = self.currency_id.round(sign * doc_base) if doc_base else 0.0
        base_c = self.company_currency_id.round(
            self.currency_id._convert(
                sign * doc_base,
                self.company_currency_id,
                self.company_id,
                self.date,
            )
        ) if doc_base else 0.0
        if include_base:
            return (base_s, base_c, igtf_currency, igtf_company)
        return igtf_currency, igtf_company

    def _l10n_ve_igtf_resync_payment_term_lines(self):
        for move in self:
            if move.state != "draft" or not move.is_invoice(include_receipts=True):
                continue
            if not move._l10n_ve_igtf_move_applies():
                continue
            need = move.needed_terms
            if not need:
                continue
            payment_term_lines = move.line_ids.filtered(
                lambda al: al.display_type == "payment_term"
            )
            for line in payment_term_lines:
                key = line.term_key
                val = need.get(key) if key in need else None
                if val is None and key is not False:
                    for fk, v in need.items():
                        if not fk:
                            continue
                        if fields.Date.to_date(
                            line.date_maturity
                        ) != fk.get("date_maturity"):
                            continue
                        mid = fk.get("move_id")
                        if mid not in (None, False) and mid not in (
                            move.id,
                            move._origin.id,
                        ):
                            continue
                        val = v
                        break
                if not val:
                    continue
                wdict = {
                    "balance": val["balance"],
                    "amount_currency": val["amount_currency"],
                }
                if "discount_balance" in val:
                    wdict["discount_balance"] = val["discount_balance"]
                if "discount_amount_currency" in val:
                    wdict["discount_amount_currency"] = val["discount_amount_currency"]
                if "discount_date" in val:
                    wdict["discount_date"] = val["discount_date"]
                line.with_context(check_move_validity=False).write(wdict)

    def _l10n_ve_igtf_recompute_invoice_lines(self):
        for move in self:
            if self.env.context.get("l10n_ve_igtf_skip_igtf"):
                continue
            to_remove = move._l10n_ve_igtf_aml()
            if to_remove:
                if _logger.isEnabledFor(logging.INFO):
                    _logger.info(
                        "l10n_ve_igtf recompute: move=%s unlink_igtf_lines=%s",
                        move.id,
                        to_remove.ids,
                    )
                to_remove.with_context(l10n_ve_igtf_skip_igtf=True).unlink()
            if not move._l10n_ve_igtf_should_add_move_lines() or not move.id:
                if _logger.isEnabledFor(logging.INFO):
                    _logger.info(
                        "l10n_ve_igtf recompute: move=%s skip (should_add=%s or no id)",
                        move.id,
                        move._l10n_ve_igtf_should_add_move_lines() if move.id else False,
                    )
                if to_remove:
                    move._l10n_ve_igtf_resync_payment_term_lines()
                continue
            company = move.company_id
            igtf_account = company.l10n_ve_igtf_account_id
            refund_line_amounts = None
            if move.move_type == "out_refund" and move.reversed_entry_id:
                refund_line_amounts = (
                    move._l10n_ve_igtf_get_refund_igtf_line_amounts_from_origin()
                )
            if refund_line_amounts:
                am_cur, bal = refund_line_amounts
            else:
                p = (company.l10n_ve_igtf_percent or 0.0) / 100.0
                doc_base = move._l10n_ve_igtf_get_document_base_total_in_currency()
                m_sign = 1.0
                if move.move_type == "out_refund":
                    m_sign = -1.0
                am_cur = -1.0 * m_sign * move.currency_id.round(doc_base * p)
                if move.currency_id.is_zero(am_cur):
                    continue
                bal = company.currency_id.round(
                    move.currency_id._convert(
                        am_cur, company.currency_id, company, move.date
                    )
                )
            if move.currency_id.is_zero(am_cur) and company.currency_id.is_zero(bal):
                continue
            if _logger.isEnabledFor(logging.INFO):
                _logger.info(
                    "l10n_ve_igtf recompute: move=%s create aml from_origin=%s "
                    "am_cur=%s bal=%s",
                    move.id,
                    bool(refund_line_amounts),
                    am_cur,
                    bal,
                )
            self.env["account.move.line"].with_context(
                l10n_ve_igtf_skip_igtf=True,
                check_move_validity=False,
            ).create(
                {
                    "move_id": move.id,
                    "account_id": igtf_account.id,
                    "name": _("IGTF %s%%") % (company.l10n_ve_igtf_percent or 0,),
                    "display_type": "l10n_ve_igtf",
                    "partner_id": move.partner_id.commercial_partner_id.id,
                    "currency_id": move.currency_id.id,
                    "amount_currency": am_cur,
                    "balance": bal,
                }
            )
            move._l10n_ve_igtf_resync_payment_term_lines()
            if _logger.isEnabledFor(logging.INFO):
                amls = move.line_ids.filtered("account_id")
                sum_bal = sum(amls.mapped("balance"))
                _logger.info(
                    "l10n_ve_igtf recompute: move=%s after_create sum(balance_aml)=%s "
                    "lines=%s",
                    move.id,
                    sum_bal,
                    [
                    (ln.id, ln.account_id.code, ln.debit, ln.credit, ln.balance)
                    for ln in amls
                ],
                )

    def _recompute_cash_rounding_lines(self):
        for move in self:
            super(AccountMove, move)._recompute_cash_rounding_lines()
        if self.env.context.get("l10n_ve_igtf_skip_igtf"):
            return
        for move in self:
            if move.state == "draft":
                move._l10n_ve_igtf_recompute_invoice_lines()

    def action_post(self):
        for move in self:
            if move.state != "draft" or self.env.context.get("l10n_ve_igtf_skip_igtf"):
                continue
            if move._l10n_ve_igtf_should_add_move_lines():
                move._l10n_ve_igtf_recompute_invoice_lines()
            elif move.l10n_ve_igtf_invoice_has_igtf_accrual():
                move._l10n_ve_igtf_resync_payment_term_lines()
        return super().action_post()

    def _reverse_moves(self, default_values_list=None, cancel=False):
        credit_notes = super()._reverse_moves(
            default_values_list=default_values_list, cancel=cancel
        )
        for move in credit_notes.filtered(
            lambda m: m.move_type == "out_refund" and m.state == "draft"
        ):
            if move._l10n_ve_igtf_should_add_move_lines():
                move._l10n_ve_igtf_recompute_invoice_lines()
        return credit_notes

    def _l10n_ve_force_refund_to_company_currency(self):
        res = super()._l10n_ve_force_refund_to_company_currency()
        refunds = self.filtered(
            lambda m: m.move_type == "out_refund" and m.state == "draft"
        )
        for move in refunds:
            igtf_lines = move._l10n_ve_igtf_aml()
            if igtf_lines:
                igtf_lines.with_context(l10n_ve_igtf_skip_igtf=True).unlink()
            if move._l10n_ve_igtf_should_add_move_lines():
                move._l10n_ve_igtf_recompute_invoice_lines()
            else:
                move.invalidate_recordset(
                    [
                        "tax_totals",
                        "l10n_ve_igtf_collected_amount_currency",
                        "l10n_ve_igtf_collected_amount_company_currency",
                    ]
                )
        return res

    def l10n_ve_igtf_invoice_has_igtf_accrual(self):
        self.ensure_one()
        if not self._l10n_ve_igtf_move_applies() or not self.is_sale_document(
            include_receipts=True
        ):
            return False
        lines = self._l10n_ve_igtf_aml()
        if not lines:
            return False
        if (
            self.move_type == "out_refund"
            and self.currency_id == self.company_currency_id
        ):
            return not self.currency_id.is_zero(
                self.currency_id.round(sum(lines.mapped("amount_currency")))
            )
        if not self.currency_id or self.currency_id not in self.company_id.l10n_ve_igtf_currency_ids:
            return False
        return not self.currency_id.is_zero(
            self.currency_id.round(sum(lines.mapped("amount_currency")))
        )

    def l10n_ve_igtf_document_has_igtf(self):
        self.ensure_one()
        if self.l10n_ve_igtf_invoice_has_igtf_accrual():
            return True
        if self.move_type == "out_refund" and self.reversed_entry_id:
            return self.reversed_entry_id._l10n_ve_igtf_origin_has_igtf()
        return False

    def _l10n_ve_igtf_origin_has_igtf(self):
        self.ensure_one()
        if self.l10n_ve_igtf_invoice_has_igtf_accrual():
            return True
        igtf_cur, igtf_comp = self._l10n_ve_igtf_get_collected_amounts(
            include_base=False
        )
        return (not self.currency_id.is_zero(igtf_cur)) or (
            not self.company_currency_id.is_zero(igtf_comp)
        )

    def _l10n_ve_igtf_refund_from_foreign_origin_in_company_currency(self):
        self.ensure_one()
        origin = self.reversed_entry_id
        return bool(
            self.move_type == "out_refund"
            and origin
            and self.currency_id == self.company_currency_id
            and origin.currency_id != origin.company_currency_id
        )

    def _l10n_ve_igtf_convert_origin_document_amount_to_refund_currency(
        self, origin, amount
    ):
        self.ensure_one()
        company = self.company_id
        if origin.currency_id == self.currency_id:
            return self.currency_id.round(amount)
        origin_date = origin.invoice_date or origin.date or fields.Date.context_today(
            self
        )
        if self.currency_id == company.currency_id:
            return company.currency_id.round(
                origin.currency_id._convert(
                    amount, company.currency_id, company, origin_date
                )
            )
        refund_date = self.invoice_date or self.date or origin_date
        return self.currency_id.round(
            origin.currency_id._convert(
                amount, self.currency_id, company, refund_date
            )
        )

    def _l10n_ve_igtf_get_refund_ratio_from_origin(self):
        self.ensure_one()
        origin = self.reversed_entry_id
        if self.move_type != "out_refund" or not origin:
            return 0.0
        if self._l10n_ve_igtf_refund_from_foreign_origin_in_company_currency():
            company_cur = self.company_currency_id
            origin_base_comp = abs(
                self._l10n_ve_igtf_convert_origin_document_amount_to_refund_currency(
                    origin,
                    origin._l10n_ve_igtf_get_document_base_total_in_currency(),
                )
            )
            credit_base_comp = abs(
                self._l10n_ve_igtf_get_document_base_total_in_currency()
            )
            if company_cur.is_zero(origin_base_comp) or company_cur.is_zero(
                credit_base_comp
            ):
                return 0.0
            return min(1.0, credit_base_comp / origin_base_comp)
        origin_base = origin._l10n_ve_igtf_get_document_base_total_in_currency()
        if origin.currency_id.is_zero(origin_base):
            return 0.0
        credit_base = self._l10n_ve_igtf_get_document_base_total_in_currency()
        if self.currency_id.is_zero(credit_base):
            return 0.0
        ratio = abs(credit_base) / abs(origin_base)
        return min(1.0, ratio)

    def _l10n_ve_igtf_get_origin_igtf_line_totals(self):
        self.ensure_one()
        if self.l10n_ve_igtf_invoice_has_igtf_accrual():
            lines = self._l10n_ve_igtf_aml()
            return (
                self.currency_id.round(sum(lines.mapped("amount_currency"))),
                self.company_currency_id.round(sum(lines.mapped("balance"))),
            )
        (
            _origin_base_cur,
            _origin_base_comp,
            origin_igtf_cur,
            origin_igtf_comp,
        ) = self._l10n_ve_igtf_get_collected_amounts(include_base=True)
        return origin_igtf_cur, origin_igtf_comp

    def _l10n_ve_igtf_get_refund_igtf_line_amounts_from_origin(self):
        self.ensure_one()
        origin = self.reversed_entry_id
        if self.move_type != "out_refund" or not origin:
            return None
        if not origin._l10n_ve_igtf_origin_has_igtf():
            return None
        ratio = self._l10n_ve_igtf_get_refund_ratio_from_origin()
        if float_compare(ratio, 0.0, precision_rounding=self.currency_id.rounding) <= 0:
            return None
        origin_igtf_cur, origin_igtf_comp = origin._l10n_ve_igtf_get_origin_igtf_line_totals()
        amount_currency = self.currency_id.round(-origin_igtf_cur * ratio)
        balance = self.company_currency_id.round(-origin_igtf_comp * ratio)
        if self._l10n_ve_igtf_refund_from_foreign_origin_in_company_currency():
            amount_currency = balance
        if self.currency_id.is_zero(amount_currency) and self.company_currency_id.is_zero(
            balance
        ):
            return None
        return amount_currency, balance

    def _l10n_ve_igtf_get_refund_igtf_amounts_from_origin(self, include_base=False):
        self.ensure_one()
        zero4 = (0.0, 0.0, 0.0, 0.0)
        zero2 = (0.0, 0.0)
        origin = self.reversed_entry_id
        if self.move_type != "out_refund" or not origin:
            return zero4 if include_base else zero2
        if not origin._l10n_ve_igtf_origin_has_igtf():
            return zero4 if include_base else zero2
        line_amounts = self._l10n_ve_igtf_get_refund_igtf_line_amounts_from_origin()
        if not line_amounts:
            return zero4 if include_base else zero2
        igtf_cur, igtf_comp = line_amounts
        sign = -1.0
        credit_doc_base = self._l10n_ve_igtf_get_document_base_total_in_currency()
        base_cur = self.currency_id.round(sign * credit_doc_base)
        if self._l10n_ve_igtf_refund_from_foreign_origin_in_company_currency():
            base_comp = base_cur
        else:
            base_comp = self.company_currency_id.round(
                self.currency_id._convert(
                    base_cur,
                    self.company_currency_id,
                    self.company_id,
                    self.date,
                )
            )
        if include_base:
            return base_cur, base_comp, igtf_cur, igtf_comp
        return igtf_cur, igtf_comp

    def l10n_ve_igtf_get_residual_excluding_igtf_in_document_currency(self):
        self.ensure_one()
        if not self.l10n_ve_igtf_invoice_has_igtf_accrual():
            return self.amount_residual
        base_total = self.l10n_ve_igtf_get_wo_igtf_total_in_document_currency()
        paid_base = self._l10n_ve_igtf_get_payment_allocation_in_document_currency()[
            "base_paid"
        ]
        residual_without_igtf = max(base_total - paid_base, 0.0)
        return self.currency_id.round(residual_without_igtf)

    def l10n_ve_igtf_get_wo_igtf_total_in_document_currency(self):
        self.ensure_one()
        if not self.l10n_ve_igtf_invoice_has_igtf_accrual():
            return self.currency_id.round(abs(self.amount_total))
        d_inv = sum(self._l10n_ve_igtf_aml().mapped("amount_currency"))
        return self.currency_id.round(self.amount_total + d_inv)

    def l10n_ve_igtf_is_counterpart_line_bs_payment(self, other_line):
        m = other_line.move_id
        p = m.origin_payment_id
        st = m.statement_line_id
        comp = self.company_id.currency_id
        if p is not None:
            return (p.currency_id or comp) == comp
        if st is not None and st.journal_id:
            j = st.journal_id
            return (j.currency_id or comp) == comp and not st.foreign_currency_id
        return False

    def _l10n_ve_igtf_cumulative_bs_paid_in_document_currency_with_stats(self):
        self.ensure_one()
        n_partial = 0
        n_included = 0
        if not self.l10n_ve_igtf_invoice_has_igtf_accrual():
            return 0.0, 0, 0
        total = 0.0
        for line in self.line_ids.filtered(
            lambda al: al.display_type == "payment_term"
            and al.account_id.account_type in ("asset_receivable", "liability_payable")
        ):
            for partial in line.matched_credit_ids | line.matched_debit_ids:
                if partial.exchange_move_id:
                    continue
                if partial.debit_move_id == line:
                    oline = partial.credit_move_id
                    amt = partial.debit_amount_currency
                elif partial.credit_move_id == line:
                    oline = partial.debit_move_id
                    amt = partial.credit_amount_currency
                else:
                    continue
                n_partial += 1
                is_bs = bool(
                    oline and self.l10n_ve_igtf_is_counterpart_line_bs_payment(oline)
                )
                if not oline or not is_bs:
                    if _logger.isEnabledFor(logging.DEBUG) and oline and self.id:
                        p_cur = oline.move_id.origin_payment_id
                        p_cur = p_cur.currency_id.name if p_cur else None
                        st = oline.move_id.statement_line_id
                        st_fx = (
                            st.foreign_currency_id.name
                            if st and st.foreign_currency_id
                            else None
                        )
                        _logger.debug(
                            "l10n_ve_igtf BS cumul skip: move=%s partial=%s omove=%s is_bs=%s p_cur=%s st_fx=%s",
                            self.id,
                            partial.id,
                            oline.move_id.id,
                            is_bs,
                            p_cur,
                            st_fx,
                        )
                    continue
                n_included += 1
                if _logger.isEnabledFor(logging.DEBUG) and self.id:
                    _logger.debug(
                        "l10n_ve_igtf BS cumul +amt move=%s partial=%s abs_amt=%s omove=%s",
                        self.id,
                        partial.id,
                        abs(amt),
                        oline.move_id.id,
                    )
                total += abs(amt)
        r = self.currency_id.round(total)
        if _logger.isEnabledFor(logging.DEBUG):
            _logger.debug(
                "l10n_ve_igtf_cumulative_bs move=%s name=%s rounded=%s n_partial=%s n_bs=%s %s",
                self.id,
                (self.name or "-")[:64],
                r,
                n_partial,
                n_included,
                self.currency_id.name,
            )
        return r, n_partial, n_included

    def l10n_ve_igtf_get_cumulative_bs_paid_in_document_currency(self):
        r, _p, _i = self._l10n_ve_igtf_cumulative_bs_paid_in_document_currency_with_stats()
        return r

    def l10n_ve_igtf_get_cumulative_base_paid_in_document_currency(self):
        self.ensure_one()
        if not self.l10n_ve_igtf_invoice_has_igtf_accrual():
            return 0.0
        return self._l10n_ve_igtf_get_payment_allocation_in_document_currency()[
            "base_paid"
        ]

    def _l10n_ve_igtf_get_payment_allocation_in_document_currency(self):
        self.ensure_one()
        result = {
            "base_paid": 0.0,
            "base_paid_bs": 0.0,
            "base_paid_outside_bs": 0.0,
            "igtf_paid_bs": 0.0,
        }
        if not self.l10n_ve_igtf_invoice_has_igtf_accrual():
            return result
        total = 0.0
        total_bs = 0.0
        total_outside_bs = 0.0
        for line in self.line_ids.filtered(
            lambda al: al.display_type == "payment_term"
            and al.account_id.account_type in ("asset_receivable", "liability_payable")
        ):
            for partial in line.matched_credit_ids | line.matched_debit_ids:
                if partial.exchange_move_id:
                    continue
                if partial.debit_move_id == line:
                    oline = partial.credit_move_id
                    amt = partial.debit_amount_currency
                elif partial.credit_move_id == line:
                    oline = partial.debit_move_id
                    amt = partial.credit_amount_currency
                else:
                    continue
                amount = abs(amt)
                total += amount
                if oline and self.l10n_ve_igtf_is_counterpart_line_bs_payment(oline):
                    total_bs += amount
                else:
                    total_outside_bs += amount
        base_total = self.l10n_ve_igtf_get_wo_igtf_total_in_document_currency()
        base_paid_outside_bs = min(total_outside_bs, base_total)
        base_left_for_bs = max(base_total - base_paid_outside_bs, 0.0)
        base_paid_bs = min(total_bs, base_left_for_bs)
        result["base_paid_outside_bs"] = self.currency_id.round(base_paid_outside_bs)
        result["base_paid_bs"] = self.currency_id.round(base_paid_bs)
        result["igtf_paid_bs"] = self.currency_id.round(max(total_bs - base_paid_bs, 0.0))
        result["base_paid"] = self.currency_id.round(
            min(base_paid_outside_bs + base_paid_bs, base_total)
        )
        return result

    def l10n_ve_igtf_get_bs_payable_igtf_residual_in_document_currency(self):
        self.ensure_one()
        if not self.l10n_ve_igtf_invoice_has_igtf_accrual():
            return 0.0
        rate = (self.company_id.l10n_ve_igtf_percent or 0.0) / 100.0
        if not rate:
            return 0.0
        allocation = self._l10n_ve_igtf_get_payment_allocation_in_document_currency()
        base_paid_outside_bs = allocation["base_paid_outside_bs"]
        igtf_from_foreign_base = self.currency_id.round(base_paid_outside_bs * rate)
        residual = max(igtf_from_foreign_base - allocation["igtf_paid_bs"], 0.0)
        return self.currency_id.round(min(residual, abs(self.amount_residual)))

    def _l10n_ve_igtf_get_collected_amounts(self, include_base=False):
        self.ensure_one()

        if not self._l10n_ve_igtf_move_applies():
            if include_base:
                return 0.0, 0.0, 0.0, 0.0
            return 0.0, 0.0

        if not self.is_sale_document(include_receipts=True):
            if include_base:
                return 0.0, 0.0, 0.0, 0.0
            return 0.0, 0.0

        company = self.company_id
        if not company.l10n_ve_igtf_account_id:
            if include_base:
                return 0.0, 0.0, 0.0, 0.0
            return 0.0, 0.0

        percent = company.l10n_ve_igtf_percent or 0.0
        if percent <= 0.0:
            if include_base:
                return 0.0, 0.0, 0.0, 0.0
            return 0.0, 0.0

        sign = 1.0
        if self.move_type == "out_refund":
            sign = -1.0

        p = percent / 100.0
        invoice_currency = self.currency_id
        if self.l10n_ve_igtf_invoice_has_igtf_accrual():
            return self._l10n_ve_igtf_get_from_invoice_igtf_lines(
                include_base=include_base
            )

        if self.move_type == "out_refund" and self.reversed_entry_id:
            origin_amounts = self._l10n_ve_igtf_get_refund_igtf_amounts_from_origin(
                include_base=include_base
            )
            if include_base:
                if not self.currency_id.is_zero(
                    origin_amounts[2]
                ) or not self.company_currency_id.is_zero(origin_amounts[3]):
                    return origin_amounts
            elif not self.currency_id.is_zero(
                origin_amounts[0]
            ) or not self.company_currency_id.is_zero(origin_amounts[1]):
                return origin_amounts

        doc_base = self._l10n_ve_igtf_get_document_base_total_in_currency()
        invoice_total = invoice_currency.round(doc_base) if doc_base else 0.0
        if invoice_currency.is_zero(invoice_total):
            if include_base:
                return 0.0, 0.0, 0.0, 0.0
            return 0.0, 0.0

        receivable_lines = self.line_ids.filtered(
            lambda line: line.account_id.account_type == "asset_receivable"
        )
        partials = (
            receivable_lines.matched_debit_ids | receivable_lines.matched_credit_ids
        ).filtered(
            lambda pr: (
                not pr.exchange_move_id
                or pr.debit_move_id.payment_id
                or pr.credit_move_id.payment_id
            )
        )
        if not partials:
            if include_base:
                return 0.0, 0.0, 0.0, 0.0
            return 0.0, 0.0

        by_pay_line = {}
        for pr in partials:
            pay_line = (
                pr.debit_move_id
                if pr.debit_move_id.payment_id
                else pr.credit_move_id
                if pr.credit_move_id.payment_id
                else False
            )
            if not pay_line:
                continue
            payment = pay_line.payment_id
            if not payment or not payment.exists() or not payment.l10n_ve_apply_igtf:
                continue
            entry = by_pay_line.setdefault(
                pay_line, {"payment": payment, "net_invoice": 0.0}
            )
            line_currency = (
                pr.debit_currency_id
                if pr.debit_move_id == pay_line
                else pr.credit_currency_id
            )
            amt = (
                abs(pr.debit_amount_currency)
                if pr.debit_move_id == pay_line
                else abs(pr.credit_amount_currency)
            )
            entry["net_invoice"] += (
                amt
                if line_currency == invoice_currency
                else line_currency._convert(amt, invoice_currency, company, pr.max_date)
            )

        if not by_pay_line:
            if include_base:
                return 0.0, 0.0, 0.0, 0.0
            return 0.0, 0.0

        base_total = 0.0
        for pay_line, data in by_pay_line.items():
            payment = data["payment"]
            net_invoice = invoice_currency.round(data["net_invoice"])
            if invoice_currency.is_zero(net_invoice):
                continue

            matched_partials = (
                pay_line.matched_debit_ids | pay_line.matched_credit_ids
            ).filtered(
                lambda pr: (
                    not pr.exchange_move_id
                    or pr.debit_move_id.payment_id
                    or pr.credit_move_id.payment_id
                )
            )
            total_net = 0.0
            for pr in matched_partials:
                line_currency = (
                    pr.debit_currency_id
                    if pr.debit_move_id == pay_line
                    else pr.credit_currency_id
                )
                amt = (
                    abs(pr.debit_amount_currency)
                    if pr.debit_move_id == pay_line
                    else abs(pr.credit_amount_currency)
                )
                total_net += (
                    amt
                    if line_currency == invoice_currency
                    else line_currency._convert(
                        amt, invoice_currency, company, pr.max_date
                    )
                )
            total_net = invoice_currency.round(total_net)
            if invoice_currency.is_zero(total_net):
                continue

            payment_amount_invoice_currency = (
                payment.amount
                if payment.currency_id == invoice_currency
                else payment.currency_id._convert(
                    payment.amount, invoice_currency, company, payment.date
                )
            )
            payment_amount_invoice_currency = invoice_currency.round(
                payment_amount_invoice_currency
            )
            if invoice_currency.is_zero(payment_amount_invoice_currency):
                continue

            base_total += payment_amount_invoice_currency * (net_invoice / total_net)

        base_total = min(invoice_currency.round(base_total), invoice_total)
        igtf_invoice_currency = invoice_currency.round(sign * (base_total * p))
        base_total_company = company.currency_id.round(
            invoice_currency._convert(
                base_total,
                company.currency_id,
                company,
                self.date,
            )
        )
        igtf_company_currency = company.currency_id.round(sign * (base_total_company * p))
        base_total_signed = invoice_currency.round(sign * base_total)
        base_total_company_signed = company.currency_id.round(sign * base_total_company)
        if invoice_currency.is_zero(igtf_invoice_currency) and company.currency_id.is_zero(
            igtf_company_currency
        ):
            if include_base:
                return base_total_signed, base_total_company_signed, 0.0, 0.0
            return 0.0, 0.0
        if include_base:
            return (
                base_total_signed,
                base_total_company_signed,
                -igtf_invoice_currency,
                -igtf_company_currency,
            )
        return igtf_invoice_currency, igtf_company_currency

    def _l10n_ve_igtf_get_residual_company_amount(self):
        self.ensure_one()
        if not self._l10n_ve_igtf_move_applies() or not self.is_sale_document(
            include_receipts=True
        ):
            return 0.0
        percent = self.company_id.l10n_ve_igtf_percent or 0.0
        if percent <= 0.0:
            return 0.0
        doc_base = self._l10n_ve_igtf_get_document_base_total_in_currency()
        invoice_total_company = self.company_currency_id.round(
            self.currency_id._convert(
                doc_base,
                self.company_currency_id,
                self.company_id,
                self.date,
            )
        )
        max_igtf = self.company_currency_id.round(
            invoice_total_company * (percent / 100.0)
        )
        if self.l10n_ve_igtf_invoice_has_igtf_accrual():
            return 0.0
        _amt_cur, collected_company = self._l10n_ve_igtf_get_collected_amounts()
        residual = max_igtf - abs(collected_company)
        return self.company_currency_id.round(max(residual, 0.0))

    @api.depends(
        "move_type",
        "line_ids.amount_residual",
        "line_ids.amount_residual_currency",
        "country_code",
        "company_id.l10n_ve_igtf_feature_active",
        "company_id.l10n_ve_igtf_allow_invoice_accrual",
    )
    def _compute_l10n_ve_igtf_collected_amounts(self):
        """
        Compute IGTF collected fields for display purposes.

        Parameters
        ----------
        None

        Returns
        -------
        None
        """
        for move in self:
            if not move._l10n_ve_igtf_move_applies():
                move.l10n_ve_igtf_collected_amount_currency = 0.0
                move.l10n_ve_igtf_collected_amount_company_currency = 0.0
                move.l10n_ve_igtf_residual_amount_company_currency = 0.0
                continue
            amt_cur, amt_comp = move._l10n_ve_igtf_get_collected_amounts()
            move.l10n_ve_igtf_collected_amount_currency = amt_cur
            move.l10n_ve_igtf_collected_amount_company_currency = amt_comp
            move.l10n_ve_igtf_residual_amount_company_currency = (
                move._l10n_ve_igtf_get_residual_company_amount()
            )

    def l10n_ve_igtf_get_unreconcile_action(self, partial_id):
        """
        Build an action that prompts the user when unreconciling an IGTF payment.

        Parameters
        ----------
        partial_id : int
            ID of the `account.partial.reconcile` being removed from this invoice.

        Returns
        -------
        dict | bool
            An `ir.actions.act_window` dictionary to open the wizard if the payment is an IGTF payment;
            otherwise `False` to fall back to the standard behavior.
        """
        self.ensure_one()

        if not self._l10n_ve_igtf_move_applies():
            return False

        partial = self.env["account.partial.reconcile"].browse(partial_id)
        if not partial.exists():
            return False

        payment = partial.debit_move_id.payment_id or partial.credit_move_id.payment_id
        if not payment or not payment.exists():
            return False

        if not payment.l10n_ve_apply_igtf:
            return False

        return {
            "type": "ir.actions.act_window",
            "name": _("IGTF Payment"),
            "res_model": "l10n_ve_igtf.unreconcile.payment.wizard",
            "view_mode": "form",
            "views": [(False, "form")],
            "target": "new",
            "context": {
                "default_move_id": self.id,
                "default_partial_id": partial.id,
                "default_payment_id": payment.id,
            },
        }

    def _l10n_ve_igtf_get_display_tax_group_amounts_from_pos(self):
        """Punto de extensión (p. ej. l10n_ve_pos_igtf): devolver tupla 4 valores o None."""
        self.ensure_one()
        return None

    def _l10n_ve_igtf_get_display_tax_group_amounts_generic(self):
        """Origen del IGTF para tax_totals: factura, preview, POS (hook), cobros."""
        self.ensure_one()
        p = (self.company_id.l10n_ve_igtf_percent or 0.0) / 100.0
        doc = self._l10n_ve_igtf_get_document_base_total_in_currency()
        m_sign = -1.0 if self.move_type == "out_refund" else 1.0
        if self._l10n_ve_igtf_aml():
            return self._l10n_ve_igtf_get_from_invoice_igtf_lines(
                include_base=True
            )
        if (
            self.move_type == "out_refund"
            and self.reversed_entry_id
            and self.reversed_entry_id._l10n_ve_igtf_origin_has_igtf()
        ):
            origin_amounts = self._l10n_ve_igtf_get_refund_igtf_amounts_from_origin(
                include_base=True
            )
            if not self.currency_id.is_zero(
                origin_amounts[2]
            ) or not self.company_currency_id.is_zero(origin_amounts[3]):
                return origin_amounts
        if self._l10n_ve_igtf_should_add_move_lines() and doc and p:
            b_loc = self.currency_id.round(m_sign * doc)
            b_comp = self.company_currency_id.round(
                self.currency_id._convert(
                    b_loc, self.company_currency_id, self.company_id, self.date
                )
            )
            am_cur = -1.0 * m_sign * self.currency_id.round(doc * p)
            am_b = self.company_currency_id.round(
                self.currency_id._convert(
                    am_cur, self.company_currency_id, self.company_id, self.date
                )
            )
            return (b_loc, b_comp, am_cur, am_b)
        pos_tuple = self._l10n_ve_igtf_get_display_tax_group_amounts_from_pos()
        if pos_tuple is not None:
            return pos_tuple
        return self._l10n_ve_igtf_get_collected_amounts(include_base=True)

    def _l10n_ve_igtf_get_display_tax_group_amounts(self):
        self.ensure_one()
        return self._l10n_ve_igtf_get_display_tax_group_amounts_generic()

    def _l10n_ve_igtf_tax_totals_should_show_igtf_row_extra(self):
        """Extender en otros módulos (POS) si hay IGTF fuera de moneda/líneas de factura."""
        return False

    def _l10n_ve_igtf_tax_totals_should_show_igtf_row(self):
        self.ensure_one()
        if not self._l10n_ve_igtf_move_applies():
            return False
        if self.currency_id in self.company_id.l10n_ve_igtf_currency_ids:
            return True
        if self._l10n_ve_igtf_aml():
            return True
        if (
            self.move_type == "out_refund"
            and self.reversed_entry_id
            and self.reversed_entry_id._l10n_ve_igtf_origin_has_igtf()
        ):
            return True
        if bool(self._l10n_ve_igtf_tax_totals_should_show_igtf_row_extra()):
            return True
        amt_cur, amt_comp = self._l10n_ve_igtf_get_collected_amounts(
            include_base=False
        )
        return (not self.currency_id.is_zero(amt_cur)) or (
            not self.company_currency_id.is_zero(amt_comp)
        )

    def _l10n_ve_igtf_tax_totals_row_amounts(
        self,
        igtf_base_amount_currency,
        igtf_base_amount_company_currency,
        igtf_amount_currency,
        igtf_amount_company_currency,
    ):
        self.ensure_one()
        if self.move_type == "out_refund":
            return (
                abs(igtf_base_amount_currency),
                abs(igtf_base_amount_company_currency),
                abs(igtf_amount_currency),
                abs(igtf_amount_company_currency),
                igtf_amount_currency,
                igtf_amount_company_currency,
            )
        return (
            igtf_base_amount_currency,
            igtf_base_amount_company_currency,
            -igtf_amount_currency,
            -igtf_amount_company_currency,
            -igtf_amount_currency,
            -igtf_amount_company_currency,
        )

    def _l10n_ve_igtf_tax_totals_merge_igtf_row(self):
        """Devuelve tax_totals enriquecido o False si no aplica."""
        self.ensure_one()

        def _log_skip(reason, **extra):
            if self._l10n_ve_igtf_move_applies() and self.is_invoice(
                include_receipts=True
            ):
                tt = self.tax_totals or {}
                _logger.info(
                    "l10n_ve_igtf tax_totals skip move_id=%s name=%s reason=%s "
                    "tax_totals_keys=%s extra=%s",
                    self.id,
                    self.name or "",
                    reason,
                    list(tt.keys()),
                    extra,
                )
            return False

        if not self._l10n_ve_igtf_move_applies():
            return False
        if (
            not self.tax_totals
            or not self.is_invoice(include_receipts=True)
            or not self.is_sale_document(include_receipts=True)
        ):
            return _log_skip(
                "no_tax_totals_or_not_invoice",
                has_tax_totals=bool(self.tax_totals),
                is_invoice=self.is_invoice(include_receipts=True),
                is_sale=self.is_sale_document(include_receipts=True),
            )
        if not self.currency_id:
            return _log_skip("no_currency_id")
        if not self._l10n_ve_igtf_tax_totals_should_show_igtf_row():
            return _log_skip(
                "should_show_false",
                currency_in_igtf_currencies=self.currency_id
                in self.company_id.l10n_ve_igtf_currency_ids,
                has_igtf_aml=bool(self._l10n_ve_igtf_aml()),
                extra_pos_like=bool(
                    self._l10n_ve_igtf_tax_totals_should_show_igtf_row_extra()
                ),
            )
        if "l10n_ve_igtf_total_without_igtf_currency" in (self.tax_totals or {}):
            return False
        igtf_label = _("IGTF %(percent)s %%")
        (
            igtf_base_amount_currency,
            igtf_base_amount_company_currency,
            igtf_amount_currency,
            igtf_amount_company_currency,
        ) = self._l10n_ve_igtf_get_display_tax_group_amounts_generic()
        if self.currency_id.is_zero(
            igtf_amount_currency
        ) and self.company_currency_id.is_zero(igtf_amount_company_currency):
            return _log_skip(
                "zero_igtf_amounts",
                generic_tuple=(
                    igtf_base_amount_currency,
                    igtf_base_amount_company_currency,
                    igtf_amount_currency,
                    igtf_amount_company_currency,
                ),
            )
        totals = dict(self.tax_totals)
        total_doc_before_igtf = totals.get("total_amount_currency", 0.0)
        total_comp_before_igtf = totals.get("total_amount", 0.0)
        subtotals = list(totals.get("subtotals") or [])
        percent = self.company_id.l10n_ve_igtf_percent or 0
        percent_str = int(percent) if percent == int(percent) else percent
        (
            row_base_currency,
            row_base_company,
            row_tax_currency,
            row_tax_company,
            collected_currency,
            collected_company,
        ) = self._l10n_ve_igtf_tax_totals_row_amounts(
            igtf_base_amount_currency,
            igtf_base_amount_company_currency,
            igtf_amount_currency,
            igtf_amount_company_currency,
        )
        igtf_tax_group = {
            "id": -1,
            "involved_tax_ids": [],
            "group_name": igtf_label % {"percent": percent_str},
            "group_label": False,
            "base_amount_currency": row_base_currency,
            "display_base_amount_currency": row_base_currency,
            "tax_amount_currency": row_tax_currency,
            "base_amount": row_base_company,
            "display_base_amount": row_base_company,
            "tax_amount": row_tax_company,
        }
        if subtotals:
            last_subtotal = subtotals[-1]
            last_subtotal["tax_groups"] = list(
                last_subtotal.get("tax_groups") or []
            ) + [igtf_tax_group]
        else:
            subtotals.append(
                {
                    "name": _("Untaxed Amount"),
                    "base_amount_currency": row_base_currency,
                    "base_amount": row_base_company,
                    "tax_amount_currency": 0.0,
                    "tax_amount": 0.0,
                    "tax_groups": [igtf_tax_group],
                }
            )
        totals["subtotals"] = subtotals
        totals["l10n_ve_igtf_collected_amount_currency"] = collected_currency
        totals["l10n_ve_igtf_collected_amount"] = collected_company
        if self.move_type == "out_refund":
            igtf_total_delta_currency = abs(igtf_amount_currency)
            igtf_total_delta_company = abs(igtf_amount_company_currency)
        else:
            igtf_total_delta_currency = -igtf_amount_currency
            igtf_total_delta_company = -igtf_amount_company_currency
        totals["total_amount_currency"] = (
            totals.get("total_amount_currency", 0.0) + igtf_total_delta_currency
        )
        totals["total_amount"] = (
            totals.get("total_amount", 0.0) + igtf_total_delta_company
        )
        totals["l10n_ve_igtf_total_without_igtf_currency"] = total_doc_before_igtf
        totals["l10n_ve_igtf_total_without_igtf"] = total_comp_before_igtf
        if self._l10n_ve_igtf_move_applies():
            _logger.info(
                "l10n_ve_igtf tax_totals merged move_id=%s name=%s "
                "subtotals_len=%s total_amount_currency=%s igtf_tax_currency=%s",
                self.id,
                self.name or "",
                len(totals.get("subtotals") or []),
                totals.get("total_amount_currency"),
                igtf_tax_group.get("tax_amount_currency"),
            )
        return totals

    @api.depends_context("lang")
    @api.depends(
        "invoice_line_ids.currency_rate",
        "invoice_line_ids.tax_base_amount",
        "invoice_line_ids.tax_line_id",
        "invoice_line_ids.price_total",
        "invoice_line_ids.price_subtotal",
        "invoice_payment_term_id",
        "partner_id",
        "currency_id",
        "line_ids.amount_residual",
        "line_ids.amount_residual_currency",
        "line_ids.display_type",
        "line_ids.amount_currency",
        "line_ids.balance",
        "move_type",
        "state",
        "payment_state",
        "reversed_entry_id",
        "country_code",
        "company_id.l10n_ve_igtf_feature_active",
        "company_id.l10n_ve_igtf_allow_invoice_accrual",
    )
    def _compute_tax_totals(self):
        """
        Compute invoice tax totals and inject an IGTF row from move lines (or display preview).
        The IGTF amount is added to the total_amount in this dict to align with amount_total.
        """
        super()._compute_tax_totals()
        for move in self:
            merged = move._l10n_ve_igtf_tax_totals_merge_igtf_row()
            if merged is not False:
                move.tax_totals = merged

    @api.depends(
        "move_type",
        "line_ids.amount_residual",
        "country_code",
        "company_id.l10n_ve_igtf_feature_active",
    )
    def _compute_payments_widget_reconciled_info(self):
        """
        Enrich the invoice payments widget lines with IGTF details.

        Parameters
        ----------
        None

        Returns
        -------
        None

        Notes
        -----
        This method post-processes `invoice_payments_widget` computed by core to:
        - Show the gross paid amount on the widget line (base amount before IGTF deduction).
        - Show the IGTF amount (in payment currency and company currency) as an extra line and in the popover.
        - Allocate IGTF proportionally per invoice when a single payment is reconciled with multiple invoices.
        """
        super()._compute_payments_widget_reconciled_info()

        Partial = self.env["account.partial.reconcile"]
        Payment = self.env["account.payment"]

        for move in self:
            if not move._l10n_ve_igtf_move_applies():
                continue
            widget = move.invoice_payments_widget
            if not widget or not isinstance(widget, dict) or not widget.get("content"):
                continue

            content = widget["content"]
            lines = list(content.values()) if isinstance(content, dict) else (content or [])

            for line in lines:
                if line.get("is_exchange"):
                    continue

                payment_id = line.get("account_payment_id")
                partial_id = line.get("partial_id")
                currency_id = line.get("currency_id")
                if not payment_id or not partial_id or not currency_id:
                    continue

                payment = Payment.browse(payment_id)
                if not payment or not payment.exists():
                    continue

                igtf_account = payment.company_id.l10n_ve_igtf_account_id
                if not igtf_account:
                    continue

                partial = Partial.browse(partial_id)
                if not partial or not partial.exists():
                    continue

                widget_currency = self.env["res.currency"].browse(currency_id)

                total_igtf_company_currency = 0.0
                igtf_amls = payment.move_id.line_ids.filtered(
                    lambda line: line.account_id == igtf_account
                )
                if not igtf_amls:
                    igtf_amls = payment.move_id.line_ids.filtered(
                        lambda line: (line.name or "").upper().startswith("IGTF")
                    )
                if not igtf_amls:
                    continue

                for aml in igtf_amls:
                    total_igtf_company_currency += abs(aml.balance)

                total_igtf_company_currency = payment.company_currency_id.round(
                    total_igtf_company_currency
                )
                if payment.company_currency_id.is_zero(total_igtf_company_currency):
                    continue

                pay_line = False
                if partial.debit_move_id.payment_id == payment:
                    pay_line = partial.debit_move_id
                elif partial.credit_move_id.payment_id == payment:
                    pay_line = partial.credit_move_id
                if not pay_line:
                    continue

                net_amount = line.get("amount", 0.0)
                if widget_currency.is_zero(net_amount):
                    continue

                payment_amount_widget = (
                    payment.amount
                    if payment.currency_id == widget_currency
                    else payment.currency_id._convert(
                        payment.amount,
                        widget_currency,
                        payment.company_id,
                        payment.date,
                    )
                )
                if widget_currency.is_zero(payment_amount_widget):
                    continue

                p = (payment.company_id.l10n_ve_igtf_percent or 0.0) / 100.0
                if p <= 0.0:
                    continue

                matched_partials = (
                    pay_line.matched_debit_ids | pay_line.matched_credit_ids
                ).filtered(
                    lambda pr: (
                        not pr.exchange_move_id
                        or pr.debit_move_id.payment_id
                        or pr.credit_move_id.payment_id
                    )
                )
                total_net_paymentline_widget = 0.0
                for pr in matched_partials:
                    line_currency = (
                        pr.debit_currency_id
                        if pr.debit_move_id == pay_line
                        else pr.credit_currency_id
                    )
                    amt = (
                        abs(pr.debit_amount_currency)
                        if pr.debit_move_id == pay_line
                        else abs(pr.credit_amount_currency)
                    )
                    total_net_paymentline_widget += (
                        amt
                        if line_currency == widget_currency
                        else line_currency._convert(
                            amt, widget_currency, payment.company_id, pr.max_date
                        )
                    )
                if widget_currency.is_zero(total_net_paymentline_widget):
                    continue

                gross_allocated_widget = payment_amount_widget * (
                    net_amount / total_net_paymentline_widget
                )
                allocation_ratio = net_amount / total_net_paymentline_widget
                igtf_company_currency = payment.company_currency_id.round(
                    total_igtf_company_currency * allocation_ratio
                )
                igtf_amount_widget = widget_currency.round(
                    payment.company_currency_id._convert(
                        igtf_company_currency,
                        widget_currency,
                        payment.company_id,
                        partial.max_date,
                    )
                )

                invoice_total_widget = (
                    move.amount_total
                    if move.currency_id == widget_currency
                    else move.currency_id._convert(
                        move.amount_total, widget_currency, move.company_id, move.date
                    )
                )
                base_widget = (
                    min(gross_allocated_widget, invoice_total_widget)
                    if invoice_total_widget
                    else gross_allocated_widget
                )
                gross_amount = base_widget

                gross_company_currency = abs(
                    widget_currency._convert(
                        gross_amount,
                        payment.company_currency_id,
                        payment.company_id,
                        partial.max_date,
                    )
                )

                line.update(
                    {
                        "amount": gross_amount,
                        "l10n_ve_net_amount": net_amount,
                        "l10n_ve_igtf_amount": igtf_amount_widget,
                        "l10n_ve_net_amount_formatted": formatLang(
                            self.env, net_amount, currency_obj=widget_currency
                        ),
                        "l10n_ve_igtf_amount_formatted": formatLang(
                            self.env, igtf_amount_widget, currency_obj=widget_currency
                        ),
                        "l10n_ve_igtf_amount_company_currency_formatted": formatLang(
                            self.env,
                            igtf_company_currency,
                            currency_obj=payment.company_currency_id,
                        ),
                        "amount_foreign_currency": formatLang(
                            self.env, gross_amount, currency_obj=widget_currency
                        ),
                        "amount_company_currency": formatLang(
                            self.env,
                            gross_company_currency,
                            currency_obj=payment.company_currency_id,
                        ),
                    }
                )

    @api.depends(
        "company_id",
        "company_id.taxpayer_type",
        "company_id.l10n_ve_igtf_feature_active",
        "l10n_ve_inverse_rate",
        "move_type",
        "country_code",
    )
    def _compute_seniat_invoice_tag(self):
        super()._compute_seniat_invoice_tag()

