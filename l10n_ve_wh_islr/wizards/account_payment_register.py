# Copyright 2026 BWEALTHICS LLC
# Part of l10n_ve_wh_islr. License LGPL-3.

from odoo import Command, api, fields, models
from odoo.exceptions import UserError


class AccountPaymentRegister(models.TransientModel):
    _inherit = "account.payment.register"

    l10n_ve_islr_concept_id = fields.Many2one(
        "l10n.ve.islr.concept",
        string="Concepto ISLR",
        compute="_compute_l10n_ve_islr_concept_id",
        store=True,
        readonly=False,
    )
    l10n_ve_islr_rate = fields.Float(
        string="Tarifa ISLR (%)",
        digits=(5, 2),
        compute="_compute_l10n_ve_islr_rate",
    )
    l10n_ve_islr_base = fields.Monetary(
        string="Base ISLR",
        currency_field="currency_id",
        compute="_compute_l10n_ve_islr_base",
        store=True,
        readonly=False,
        help="Porción SIN IVA del monto pagado (el IVA no forma parte de la base "
        "de retención de ISLR del Decreto 1.808). Editable como override manual.",
    )
    l10n_ve_islr_subtrahend = fields.Monetary(
        string="Sustraendo ISLR",
        currency_field="currency_id",
        compute="_compute_l10n_ve_islr_subtrahend",
        help="UT vigente a la fecha del pago × tarifa × 83,3334 (solo PN residente), "
        "convertido de Bs a la moneda del pago.",
    )
    l10n_ve_islr_amount = fields.Monetary(
        string="Retención ISLR",
        currency_field="currency_id",
        compute="_compute_l10n_ve_islr_amount",
        store=True,
        readonly=False,
    )

    def _l10n_ve_islr_applicable(self):
        self.ensure_one()
        if not (
            self.can_edit_wizard
            and self.payment_type == "outbound"
            and self.partner_type == "supplier"
            and self.partner_id
        ):
            return False
        moves = self.line_ids.move_id
        if not moves or any(move.state != "posted" for move in moves):
            return False
        batches = self.batches
        return bool(batches) and (len(batches[0]["lines"]) == 1 or self.group_payment)

    def _l10n_ve_islr_get_bills(self):
        self.ensure_one()
        return self.line_ids.move_id.filtered(
            lambda move: move.is_purchase_document(include_receipts=True)
        )

    def _l10n_ve_islr_get_untaxed_factor(self):
        """Return the untaxed share of the wizard bills for prorating payments."""
        self.ensure_one()
        bills = self._l10n_ve_islr_get_bills()
        total = sum(abs(bill.amount_total_signed) for bill in bills)
        if not total:
            return 1.0
        return sum(abs(bill.amount_untaxed_signed) for bill in bills) / total

    @api.depends(
        "partner_id",
        "payment_type",
        "partner_type",
        "can_edit_wizard",
        "group_payment",
        "line_ids",
    )
    def _compute_l10n_ve_islr_concept_id(self):
        for wizard in self:
            if wizard._l10n_ve_islr_applicable():
                wizard.l10n_ve_islr_concept_id = (
                    wizard.partner_id.l10n_ve_islr_concept_id
                )
            else:
                wizard.l10n_ve_islr_concept_id = False

    @api.depends("l10n_ve_islr_concept_id", "partner_id.l10n_ve_person_type")
    def _compute_l10n_ve_islr_rate(self):
        for wizard in self:
            concept = wizard.l10n_ve_islr_concept_id
            if concept:
                wizard.l10n_ve_islr_rate = concept._get_rate(
                    wizard.partner_id.l10n_ve_person_type or "pj_dom"
                )
            else:
                wizard.l10n_ve_islr_rate = 0.0

    @api.depends(
        "amount",
        "currency_id",
        "l10n_ve_islr_concept_id",
        "group_payment",
        "line_ids",
    )
    def _compute_l10n_ve_islr_base(self):
        for wizard in self:
            if wizard.l10n_ve_islr_concept_id and wizard._l10n_ve_islr_applicable():
                base = wizard.amount * wizard._l10n_ve_islr_get_untaxed_factor()
                wizard.l10n_ve_islr_base = (
                    wizard.currency_id.round(base) if wizard.currency_id else base
                )
            else:
                wizard.l10n_ve_islr_base = 0.0

    @api.depends(
        "l10n_ve_islr_concept_id",
        "partner_id.l10n_ve_person_type",
        "payment_date",
        "currency_id",
    )
    def _compute_l10n_ve_islr_subtrahend(self):
        for wizard in self:
            wizard.l10n_ve_islr_subtrahend = wizard._l10n_ve_islr_get_subtrahend()

    @api.depends(
        "l10n_ve_islr_base",
        "l10n_ve_islr_rate",
        "l10n_ve_islr_subtrahend",
        "l10n_ve_islr_concept_id",
        "group_payment",
        "line_ids",
    )
    def _compute_l10n_ve_islr_amount(self):
        for wizard in self:
            if (
                not wizard.l10n_ve_islr_concept_id
                or not wizard._l10n_ve_islr_applicable()
            ):
                wizard.l10n_ve_islr_amount = 0.0
                continue
            amount = (
                wizard.l10n_ve_islr_base * wizard.l10n_ve_islr_rate / 100.0
                - wizard.l10n_ve_islr_subtrahend
            )
            wizard.l10n_ve_islr_amount = max(amount, 0.0)

    def _l10n_ve_islr_get_subtrahend(self):
        self.ensure_one()
        concept = self.l10n_ve_islr_concept_id
        if (
            not concept
            or not concept.apply_subtrahend
            or self.partner_id.l10n_ve_person_type != "pn_res"
            or not self.payment_date
            or not self.currency_id
            or not self.company_id
        ):
            return 0.0
        ut_value = self.env["l10n.ve.ut"].get_ut_value(self.payment_date)
        subtrahend_ves = ut_value * concept.rate_pn_res / 100.0 * 83.3334
        ves = self.env["l10n.ve.ut"]._require_ves_rate(
            self.company_id, self.payment_date
        )
        return ves._convert(
            subtrahend_ves,
            self.currency_id,
            self.company_id,
            self.payment_date,
        )

    def _l10n_ve_islr_check_amount(self):
        """Ensure a manually edited withholding is nonnegative and below payment."""
        self.ensure_one()
        currency = self.currency_id
        if currency.compare_amounts(self.l10n_ve_islr_amount, 0.0) < 0:
            raise UserError(self.env._("La retención ISLR no puede ser negativa."))
        if (
            currency.compare_amounts(self.l10n_ve_islr_amount, 0.0) > 0
            and currency.compare_amounts(self.l10n_ve_islr_amount, self.amount) >= 0
        ):
            raise UserError(
                self.env._(
                    "La retención ISLR (%(withholding)s) no puede ser igual o "
                    "superior al monto del pago (%(amount)s).",
                    withholding=self.l10n_ve_islr_amount,
                    amount=self.amount,
                )
            )

    def _l10n_ve_islr_get_values(self):
        self.ensure_one()
        if not self._l10n_ve_islr_applicable() or not self.l10n_ve_islr_concept_id:
            return {}
        self._l10n_ve_islr_check_amount()
        return {
            "concept": self.l10n_ve_islr_concept_id,
            "person_type": self.partner_id.l10n_ve_person_type or "pj_dom",
            "base": self.l10n_ve_islr_base,
            "rate": self.l10n_ve_islr_rate,
            "subtrahend": self.l10n_ve_islr_subtrahend,
            "amount": self.l10n_ve_islr_amount,
            "withhold": self.currency_id.compare_amounts(self.l10n_ve_islr_amount, 0.0)
            > 0,
        }

    def _create_payment_vals_from_wizard(self, batch_result):
        payment_vals = super()._create_payment_vals_from_wizard(batch_result)
        islr_vals = self._l10n_ve_islr_get_values()
        if islr_vals and islr_vals["withhold"]:
            account = self.company_id.l10n_ve_islr_wh_account_id
            if not account:
                raise UserError(
                    self.env._(
                        "Configure la Cuenta de Retenciones ISLR por Enterar en "
                        "Ajustes > Contabilidad antes de retener ISLR."
                    )
                )
            withholding = islr_vals["amount"]
            payment_vals["amount"] -= withholding
            if self.currency_id.compare_amounts(payment_vals["amount"], 0.0) <= 0:
                raise UserError(
                    self.env._(
                        "Las retenciones combinadas del pago agotan o exceden su "
                        "monto (monto restante: %(amount)s). Revise los montos de "
                        "retención editados manualmente.",
                        amount=payment_vals["amount"],
                    )
                )
            if self.payment_type == "inbound":
                write_off_amount_currency = withholding
            else:
                write_off_amount_currency = -withholding
            payment_vals.setdefault("write_off_line_vals", []).append(
                {
                    "name": self.env._("Retención ISLR %s", islr_vals["concept"].name),
                    "account_id": account.id,
                    "partner_id": self.partner_id.commercial_partner_id.id,
                    "currency_id": self.currency_id.id,
                    "amount_currency": write_off_amount_currency,
                    "balance": self.currency_id._convert(
                        write_off_amount_currency,
                        self.company_id.currency_id,
                        self.company_id,
                        self.payment_date,
                    ),
                }
            )
        return payment_vals

    def _create_payments(self):
        self.ensure_one()
        islr_vals = self._l10n_ve_islr_get_values()
        payments = super()._create_payments()
        if islr_vals:
            self._l10n_ve_islr_create_vouchers(payments, islr_vals)
        return payments

    def _l10n_ve_islr_create_vouchers(self, payments, islr_vals):
        """Create one voucher per invoice and prorate grouped payments."""
        self.ensure_one()
        currency = self.currency_id
        bills = self._l10n_ve_islr_get_bills()
        common_vals = {
            "date": self.payment_date,
            "company_id": self.company_id.id,
            "currency_id": currency.id,
            "partner_id": self.partner_id.id,
            "payment_id": payments[:1].id,
            "concept_id": islr_vals["concept"].id,
            "person_type": islr_vals["person_type"],
            "rate": islr_vals["rate"],
            "state": "issued",
        }
        keys = ("base", "subtrahend", "amount")
        vals_list = []
        if len(bills) <= 1:
            vals_list.append(
                {
                    **common_vals,
                    "move_ids": [Command.set(bills.ids)],
                    **{key: islr_vals[key] for key in keys},
                }
            )
        else:
            weights = [
                abs(bill.amount_untaxed_signed) or abs(bill.amount_total_signed)
                for bill in bills
            ]
            total_weight = sum(weights)
            totals = {key: islr_vals[key] for key in keys}
            remaining = dict(totals)
            for index, bill in enumerate(bills):
                if index == len(bills) - 1:
                    share = {key: max(value, 0.0) for key, value in remaining.items()}
                else:
                    factor = (
                        weights[index] / total_weight
                        if total_weight
                        else 1.0 / len(bills)
                    )
                    share = {key: currency.round(totals[key] * factor) for key in keys}
                    remaining = {key: remaining[key] - share[key] for key in keys}
                vals_list.append(
                    {
                        **common_vals,
                        "move_ids": [Command.set(bill.ids)],
                        **share,
                    }
                )
        return self.env["l10n.ve.islr.voucher"].sudo().create(vals_list)
