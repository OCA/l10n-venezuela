# Part of Odoo. See LICENSE file for full copyright and licensing details.

import json

from odoo import _, api, fields, models
from odoo.tools import float_compare, float_is_zero
from odoo.tools.misc import formatLang


class PosOrder(models.Model):
    _inherit = "pos.order"

    l10n_ve_manual_global_discounts = fields.Json(
        string="VE manual global discounts",
        default=list,
        help="Manual SENIAT global discounts applied in POS (no product lines).",
    )
    l10n_ve_ewallet_credit_done = fields.Boolean(
        string="VE eWallet credit done",
        copy=False,
        help="Technical flag: pay-later refund amount was already credited to eWallet.",
    )
    l10n_ve_ewallet_credited_amount = fields.Float(
        string="VE eWallet credited amount",
        copy=False,
        help="Amount in order currency already credited to eWallet from this refund.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if "l10n_ve_manual_global_discounts" in vals:
                vals["l10n_ve_manual_global_discounts"] = (
                    self._l10n_ve_normalize_manual_global_discounts(
                        vals["l10n_ve_manual_global_discounts"]
                    )
                )
        return super().create(vals_list)

    def write(self, vals):
        if "l10n_ve_manual_global_discounts" in vals:
            vals = dict(vals)
            vals["l10n_ve_manual_global_discounts"] = (
                self._l10n_ve_normalize_manual_global_discounts(
                    vals["l10n_ve_manual_global_discounts"]
                )
            )
        return super().write(vals)

    def _l10n_ve_ewallet_payment_label(self):
        return _("Monedero D")

    def _l10n_ve_ewallet_fiscal_payment_code(self):
        return "24"

    def _l10n_ve_is_ewallet_reward_line(self, line):
        reward = line.reward_id
        if not reward or not line.is_reward_line:
            return False
        program = reward.program_id
        return bool(program and program.program_type in ("ewallet", "gift_card"))

    def _l10n_ve_pos_ewallet_spend_lines(self):
        self.ensure_one()
        if "is_reward_line" not in self.lines._fields:
            return self.lines.browse()
        return self.lines.filtered(self._l10n_ve_is_ewallet_reward_line)

    def _l10n_ve_pos_ewallet_spend_amount(self, with_tax=False):
        """Ewallet/gift-card spend in order currency."""
        self.ensure_one()
        field_name = "price_subtotal_incl" if with_tax else "price_subtotal"
        amount = abs(sum(self._l10n_ve_pos_ewallet_spend_lines().mapped(field_name)))
        return self.currency_id.round(amount)

    def _l10n_ve_pos_loyalty_discount_lines(self):
        self.ensure_one()
        lines = self.lines
        if "l10n_ve_global_discount" in lines._fields:
            flagged = lines.filtered("l10n_ve_global_discount")
        else:
            flagged = lines.browse()
        if "is_reward_line" not in lines._fields:
            return flagged
        reward_discounts = lines.filtered(
            lambda line: (
                line.is_reward_line
                and line.reward_id
                and line.reward_id._l10n_ve_should_use_global_discount()
            )
        )
        return flagged | reward_discounts

    def _l10n_ve_pos_loyalty_discount_lines_excluding_ewallet(self):
        self.ensure_one()
        return self._l10n_ve_pos_loyalty_discount_lines().filtered(
            lambda line: not self._l10n_ve_is_ewallet_reward_line(line)
        )

    def _l10n_ve_pos_company_is_venezuela(self):
        self.ensure_one()
        country = (
            self.company_id.account_fiscal_country_id or self.company_id.country_id
        )
        return bool(country and country.code == "VE")

    @api.model
    def _l10n_ve_normalize_manual_global_discounts(self, value):
        """POS may send a JSON string because serialize() stringifies objects."""
        data = value
        for _attempt in range(3):
            if isinstance(data, list):
                return data
            if isinstance(data, str) and data:
                try:
                    data = json.loads(data)
                except (TypeError, ValueError, json.JSONDecodeError):
                    return []
                continue
            break
        return []

    def _l10n_ve_get_manual_global_discounts(self):
        self.ensure_one()
        return self._l10n_ve_normalize_manual_global_discounts(
            self.l10n_ve_manual_global_discounts
        )

    def _l10n_ve_manual_discount_base_lines(self):
        self.ensure_one()
        AccountTax = self.env["account.tax"]
        base_lines = []
        for discount in self._l10n_ve_get_manual_global_discounts():
            for split in discount.get("splits") or []:
                amount = abs(float(split.get("amount") or 0.0))
                if float_is_zero(amount, precision_rounding=self.currency_id.rounding):
                    continue
                tax_ids = split.get("tax_ids") or []
                taxes = AccountTax.browse([int(tax_id) for tax_id in tax_ids]).exists()
                base_lines.append(
                    AccountTax._prepare_base_line_for_taxes_computation(
                        False,
                        price_unit=-amount,
                        quantity=1.0,
                        discount=0.0,
                        tax_ids=taxes,
                        currency_id=self.currency_id,
                        partner_id=self.partner_id,
                        company_id=self.company_id,
                        sign=1,
                    )
                )
        return base_lines

    def _compute_prices(self):
        res = super()._compute_prices()
        AccountTax = self.env["account.tax"]
        for order in self:
            if not order._l10n_ve_pos_company_is_venezuela():
                continue
            if not order._l10n_ve_get_manual_global_discounts():
                continue
            if not order.currency_id:
                continue
            order.amount_paid = sum(payment.amount for payment in order.payment_ids)
            order.amount_return = -sum(
                payment.amount < 0 and payment.amount or 0
                for payment in order.payment_ids
            )
            base_lines = order.lines._prepare_tax_base_line_values()
            base_lines.extend(order._l10n_ve_manual_discount_base_lines())
            AccountTax._add_tax_details_in_base_lines(base_lines, order.company_id)
            AccountTax._round_base_lines_tax_details(base_lines, order.company_id)
            cash_rounding = None
            if (
                order.config_id.cash_rounding
                and not order.config_id.only_round_cash_method
                and order.config_id.rounding_method
            ):
                cash_rounding = order.config_id.rounding_method
            tax_totals = AccountTax._get_tax_totals_summary(
                base_lines=base_lines,
                currency=order.currency_id,
                company=order.company_id,
                cash_rounding=cash_rounding,
            )
            refund_factor = -1 if (order.amount_total < 0.0) else 1
            order.amount_tax = refund_factor * tax_totals["tax_amount_currency"]
            order.amount_total = refund_factor * tax_totals["total_amount_currency"]
            order.amount_difference = order.amount_paid - order.amount_total
        return res

    def _prepare_tax_base_line_values(self):
        values = super()._prepare_tax_base_line_values()
        if not self._l10n_ve_pos_company_is_venezuela():
            return values
        skip_ids = set(self._l10n_ve_pos_loyalty_discount_lines().ids)
        if not skip_ids:
            return values
        return [vals for vals in values if vals["record"].id not in skip_ids]

    def _create_invoice(self, move_vals):
        invoice = super()._create_invoice(move_vals)
        self._l10n_ve_pos_transfer_loyalty_discounts_to_invoice(invoice)
        self._l10n_ve_pos_set_ewallet_payment_note(invoice)
        return invoice

    def _l10n_ve_pos_set_ewallet_payment_note(self, invoice):
        self.ensure_one()
        if not invoice or not self._l10n_ve_pos_company_is_venezuela():
            return
        amount = self._l10n_ve_pos_ewallet_spend_amount(with_tax=True)
        if float_is_zero(amount, precision_rounding=self.currency_id.rounding):
            return
        label = self._l10n_ve_ewallet_payment_label()
        note = _(
            "Pagado con: %(payment)s (%(amount)s)",
            payment=label,
            amount=formatLang(self.env, amount, currency_obj=self.currency_id),
        )
        existing = invoice.narration or ""
        if label in existing:
            return
        invoice.narration = f"{existing}\n{note}".strip() if existing else note

    def _l10n_ve_pos_transfer_loyalty_discounts_to_invoice(self, invoice):
        self.ensure_one()
        if not invoice or not self._l10n_ve_pos_company_is_venezuela():
            return
        if invoice.country_code != "VE":
            return
        reason_model = self.env["l10n.ve.discount.reason"]
        default_reason = reason_model._l10n_ve_get_default()
        currency = invoice.currency_id
        PosOrderLine = self.env["pos.order.line"]

        discount_lines = self._l10n_ve_pos_loyalty_discount_lines()
        grouped = {}
        for line in discount_lines:
            key = (
                line.reward_id.id
                if line.reward_id
                else line.reward_identifier_code or line.id
            )
            grouped.setdefault(key, PosOrderLine)
            grouped[key] |= line
        for group_lines in grouped.values():
            amount = abs(sum(group_lines.mapped("price_subtotal")))
            if float_is_zero(amount, precision_rounding=currency.rounding):
                continue
            invoice._l10n_ve_apply_loyalty_global_discount(
                amount=amount,
                reason=default_reason,
                discount_type="fixed",
            )

        for discount in self._l10n_ve_get_manual_global_discounts():
            amount = abs(float(discount.get("amount") or 0.0))
            if float_is_zero(amount, precision_rounding=currency.rounding):
                continue
            reason = default_reason
            reason_id = discount.get("reason_id")
            if reason_id:
                reason = reason_model.browse(int(reason_id)).exists() or default_reason
            invoice._l10n_ve_apply_loyalty_global_discount(
                amount=amount,
                reason=reason,
                discount_type="fixed",
                amount_base=discount.get("amount_base") or "untaxed",
            )

    def _l10n_ve_convert_amount(self, amount, from_currency, to_currency):
        """Convert ``amount`` from ``from_currency`` to ``to_currency``."""
        self.ensure_one()
        if not from_currency or not to_currency or from_currency == to_currency:
            return (to_currency or from_currency or self.currency_id).round(amount)
        conversion_date = (
            fields.Date.to_date(self.date_order)
            if self.date_order
            else fields.Date.context_today(self)
        )
        return from_currency._convert(
            amount,
            to_currency,
            self.company_id,
            conversion_date,
        )

    def _l10n_ve_get_ewallet_program(self):
        self.ensure_one()
        programs = self.config_id._get_program_ids().filtered(
            lambda program: program.program_type == "ewallet"
        )
        if not programs:
            return programs
        if self.partner_id:
            card = (
                self.env["loyalty.card"]
                .sudo()
                .search(
                    [
                        ("partner_id", "=", self.partner_id.id),
                        ("program_id", "in", programs.ids),
                    ],
                    limit=1,
                    order="points desc, id desc",
                )
            )
            if card:
                return card.program_id
        foreign_programs = programs.filtered(
            lambda program: program.currency_id != self.currency_id
        )
        return foreign_programs[:1] or programs[:1]

    def _l10n_ve_is_pay_later_payment_method(self, method):
        return bool(method) and not method.journal_id

    def _l10n_ve_refunded_order_paid_on_credit(self):
        """True when the original POS order was fully settled with pay-later/credit."""
        self.ensure_one()
        max_ewallet = self._l10n_ve_get_original_non_credit_paid_amount()
        if max_ewallet is None:
            return False
        return float_is_zero(max_ewallet, precision_rounding=self.currency_id.rounding)

    def _l10n_ve_get_original_non_credit_paid_amount(self):
        """Cash/bank paid on the original order, in this refund's currency.

        Returns None when there is no linked original order (no cap).
        """
        self.ensure_one()
        original = self.refunded_order_id
        if not original:
            return None
        rounding = original.currency_id.rounding
        amount = 0.0
        for payment in original.payment_ids:
            if float_compare(payment.amount, 0.0, precision_rounding=rounding) <= 0:
                continue
            if self._l10n_ve_is_pay_later_payment_method(payment.payment_method_id):
                continue
            amount += payment.amount
        if original.currency_id != self.currency_id:
            amount = self._l10n_ve_convert_amount(
                amount, original.currency_id, self.currency_id
            )
        return self.currency_id.round(amount)

    def _l10n_ve_get_already_ewallet_credited_for_original(self):
        """eWallet amount already credited by sibling refunds of the same original."""
        self.ensure_one()
        original = self.refunded_order_id
        if not original:
            return 0.0
        sibling_refunds = (
            original.lines.mapped("refund_orderline_ids.order_id") - self
        ).filtered("l10n_ve_ewallet_credit_done")
        total = 0.0
        for refund in sibling_refunds:
            amount = refund.l10n_ve_ewallet_credited_amount
            if refund.currency_id != self.currency_id:
                amount = self._l10n_ve_convert_amount(
                    amount, refund.currency_id, self.currency_id
                )
            total += amount
        return self.currency_id.round(total)

    def _l10n_ve_get_pay_later_refund_credit_amount(self):
        """Amount to credit to eWallet from pay-later (no journal) refund payments.

        Only the non-credit portion of the original payment can become eWallet.
        Credit/pay-later on the original only cancels the receivable.
        """
        self.ensure_one()
        if (
            float_compare(
                self.amount_total, 0.0, precision_rounding=self.currency_id.rounding
            )
            >= 0
        ):
            return 0.0
        credit = 0.0
        for payment in self.payment_ids:
            method = payment.payment_method_id
            if not self._l10n_ve_is_pay_later_payment_method(method):
                continue
            if (
                float_compare(
                    payment.amount, 0.0, precision_rounding=self.currency_id.rounding
                )
                < 0
            ):
                credit += abs(payment.amount)
        credit = self.currency_id.round(credit)
        max_from_original = self._l10n_ve_get_original_non_credit_paid_amount()
        if max_from_original is None:
            return credit
        already = self._l10n_ve_get_already_ewallet_credited_for_original()
        remaining = max(max_from_original - already, 0.0)
        return self.currency_id.round(min(credit, remaining))

    def _l10n_ve_credit_ewallet_from_pay_later_refund(self):
        """Credit customer eWallet when a refund is settled with a no-journal method."""
        for order in self:
            if not order._l10n_ve_pos_company_is_venezuela():
                continue
            if order.l10n_ve_ewallet_credit_done:
                continue
            amount = order._l10n_ve_get_pay_later_refund_credit_amount()
            if float_is_zero(amount, precision_rounding=order.currency_id.rounding):
                continue
            if not order.partner_id:
                continue
            program = order._l10n_ve_get_ewallet_program()
            if not program:
                continue
            wallet_currency = program.currency_id or order.currency_id
            credit_points = order._l10n_ve_convert_amount(
                amount, order.currency_id, wallet_currency
            )
            if float_is_zero(
                credit_points, precision_rounding=wallet_currency.rounding
            ):
                continue
            LoyaltyCard = order.env["loyalty.card"].sudo()
            card = LoyaltyCard.search(
                [
                    ("program_id", "=", program.id),
                    ("partner_id", "=", order.partner_id.id),
                ],
                limit=1,
            )
            if not card:
                card = LoyaltyCard.create(
                    {
                        "program_id": program.id,
                        "partner_id": order.partner_id.id,
                        "points": 0,
                        "code": order.env["loyalty.card"]._generate_code(),
                    }
                )
            card.points += credit_points
            order.env["loyalty.history"].sudo().create(
                {
                    "card_id": card.id,
                    "description": _(
                        "Refund to eWallet from %(order)s",
                        order=order.display_name,
                    ),
                    "issued": credit_points,
                    "used": 0,
                    "order_model": order._name,
                    "order_id": order.id,
                }
            )
            order.l10n_ve_ewallet_credited_amount = amount
            order.l10n_ve_ewallet_credit_done = True

    def action_pos_order_paid(self):
        res = super().action_pos_order_paid()
        self._l10n_ve_credit_ewallet_from_pay_later_refund()
        return res

    @api.model
    def _load_pos_data_fields(self, config_id):
        fields_list = super()._load_pos_data_fields(config_id)
        if not fields_list:
            return fields_list
        if "l10n_ve_manual_global_discounts" not in fields_list:
            fields_list.append("l10n_ve_manual_global_discounts")
        return fields_list
