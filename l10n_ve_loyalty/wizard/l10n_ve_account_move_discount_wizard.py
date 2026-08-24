# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare

from ..models import l10n_ve_global_discount as l10n_ve_discount_logic


class L10nVeAccountMoveDiscountWizard(models.TransientModel):
    _name = "l10n.ve.account.move.discount.wizard"
    _description = "Venezuela invoice global discount wizard"

    move_id = fields.Many2one(
        comodel_name="account.move",
        string="Invoice",
        required=True,
        readonly=True,
    )
    company_id = fields.Many2one(related="move_id.company_id")
    currency_id = fields.Many2one(related="move_id.currency_id")
    company_currency_id = fields.Many2one(related="move_id.company_currency_id")
    move_state = fields.Selection(related="move_id.state")
    allowed_currency_ids = fields.Many2many(
        comodel_name="res.currency",
        compute="_compute_allowed_currency_ids",
    )
    discount_currency_id = fields.Many2one(
        comodel_name="res.currency",
        string="Moneda del descuento",
        domain="[('id', 'in', allowed_currency_ids)]",
    )
    discount_mode = fields.Selection(
        selection=[
            ("percentage", "Porcentaje"),
            ("amount", "Monto fijo"),
        ],
        string="Tipo de descuento",
        default="amount",
        required=True,
    )
    amount_base = fields.Selection(
        selection=[
            ("untaxed", "Subtotal"),
            ("total", "Total"),
        ],
        string="Base del monto",
        default="untaxed",
        help="Indica si el monto fijo se toma del subtotal o del total con impuestos.",
    )
    reason_id = fields.Many2one(
        comodel_name="l10n.ve.discount.reason",
        string="Razón de descuento",
        required=True,
    )
    discount_percentage = fields.Float(string="Porcentaje")
    amount = fields.Monetary(
        string="Monto",
        currency_field="discount_currency_id",
    )
    available_amount = fields.Monetary(
        string="Disponible",
        currency_field="discount_currency_id",
        compute="_compute_available_amount",
    )

    def _l10n_ve_allowed_discount_currencies(self):
        self.ensure_one()
        currencies = self.currency_id | self.company_currency_id
        usd = self.env.ref("base.USD", raise_if_not_found=False)
        if usd and usd.active:
            currencies |= usd
        company = self.company_id or self.move_id.company_id
        for field_name in ("foreign_currency_id", "currency_foreign_id"):
            if field_name in company._fields and company[field_name]:
                currencies |= company[field_name]
        return currencies

    @api.depends("move_id", "currency_id", "company_currency_id", "company_id")
    def _compute_allowed_currency_ids(self):
        for wizard in self:
            wizard.allowed_currency_ids = wizard._l10n_ve_allowed_discount_currencies()

    @api.depends(
        "move_id",
        "amount_base",
        "discount_currency_id",
        "discount_mode",
    )
    def _compute_available_amount(self):
        for wizard in self:
            move = wizard.move_id
            currency = wizard.discount_currency_id or wizard.currency_id
            if not move or not currency:
                wizard.available_amount = 0.0
                continue
            wizard.available_amount = move._l10n_ve_discount_available_in_currency(
                wizard.amount_base or "untaxed",
                currency,
            )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("move_id") and not vals.get("discount_currency_id"):
                move = self.env["account.move"].browse(vals["move_id"])
                vals["discount_currency_id"] = move.currency_id.id
        return super().create(vals_list)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        move = self.env["account.move"]
        if res.get("move_id"):
            move = self.env["account.move"].browse(res["move_id"])
        elif self.env.context.get(
            "active_model"
        ) == "account.move" and self.env.context.get("active_id"):
            move = self.env["account.move"].browse(self.env.context["active_id"])
            res["move_id"] = move.id
        if move:
            if "reason_id" in fields_list and not res.get("reason_id"):
                default_reason = self.env[
                    "l10n.ve.discount.reason"
                ]._l10n_ve_get_default()
                if default_reason:
                    res["reason_id"] = default_reason.id
            if "discount_currency_id" in fields_list and not res.get(
                "discount_currency_id"
            ):
                res["discount_currency_id"] = move.currency_id.id
        return res

    @api.onchange("move_id")
    def _onchange_move_id(self):
        if self.move_id and not self.discount_currency_id:
            self.discount_currency_id = self.move_id.currency_id

    def _l10n_ve_compute_percentage_discount_amount(self, remaining):
        self.ensure_one()
        move = self.move_id
        if move.state == "posted":
            total_subtotal = sum(remaining.values())
        else:
            subtotal_by_taxes = move._l10n_ve_global_discount_subtotal_by_taxes()
            total_subtotal = sum(subtotal_by_taxes.values())
        return move.currency_id.round(total_subtotal * self.discount_percentage)

    def _l10n_ve_amount_in_invoice_currency(self):
        self.ensure_one()
        move = self.move_id
        currency = self.discount_currency_id or self.currency_id or move.currency_id
        if not currency:
            raise UserError(_("Seleccione la moneda del descuento."))
        return move._l10n_ve_post_discount_amount_from_currency(
            self.amount,
            currency,
            amount_base=self.amount_base or "untaxed",
        )

    def _l10n_ve_compute_fixed_untaxed_amount(self, remaining):
        self.ensure_one()
        move = self.move_id
        amount_base = self.amount_base or "untaxed"
        amount_invoice = self._l10n_ve_amount_in_invoice_currency()
        if amount_base == "total":
            available_total = move._l10n_ve_discount_available_total(remaining)
            cmp_total = float_compare(
                amount_invoice,
                available_total,
                precision_digits=move.currency_id.decimal_places,
            )
            if cmp_total > 0:
                raise ValidationError(
                    _(
                        "El descuento (%(discount)s) supera el total disponible "
                        "(%(total)s)."
                    )
                    % {"discount": amount_invoice, "total": available_total}
                )
            if cmp_total == 0 and move.state != "posted":
                raise ValidationError(
                    _("No se permite un descuento del 100%% del total de la factura.")
                )
        return l10n_ve_discount_logic.l10n_ve_fixed_discount_to_untaxed(
            move,
            amount_invoice,
            amount_base,
            remaining,
        )

    def _l10n_ve_check_wizard_allowed(self):
        self.ensure_one()
        move = self.move_id
        if move.state == "posted":
            move._l10n_ve_check_post_discount_allowed()
        else:
            move._l10n_ve_check_global_discount_allowed()

    def action_apply_discount(self):
        self.ensure_one()
        move = self.move_id
        self._l10n_ve_check_wizard_allowed()
        remaining = move._l10n_ve_discount_remaining_subtotal_by_taxes()
        amount_base = self.amount_base or "untaxed"
        if self.discount_mode == "percentage":
            if float_compare(self.discount_percentage, 0.0, precision_digits=10) <= 0:
                raise UserError(_("Indique el porcentaje del descuento."))
            if float_compare(self.discount_percentage, 1.0, precision_digits=10) >= 0:
                raise ValidationError(
                    _("No se permite un descuento global del 100%% en la factura.")
                )
            if move.state != "posted" and move.l10n_ve_global_discount_ids.filtered(
                lambda discount: discount.discount_type == "percentage"
            ):
                raise ValidationError(
                    _("Solo puede existir un descuento global por porcentaje.")
                )
            amount = self._l10n_ve_compute_percentage_discount_amount(remaining)
            amount_base = "untaxed"
        else:
            if not self.amount:
                raise UserError(_("Indique el monto del descuento."))
            amount = self._l10n_ve_compute_fixed_untaxed_amount(remaining)
        if (
            float_compare(amount, 0.0, precision_digits=move.currency_id.decimal_places)
            <= 0
        ):
            raise UserError(_("El monto del descuento debe ser mayor que cero."))
        remaining_untaxed = sum(remaining.values())
        cmp_remaining = float_compare(
            amount,
            remaining_untaxed,
            precision_digits=move.currency_id.decimal_places,
        )
        if cmp_remaining > 0:
            raise ValidationError(
                _(
                    "El descuento (%(discount)s) supera el subtotal disponible "
                    "(%(subtotal)s)."
                )
                % {"discount": amount, "subtotal": remaining_untaxed}
            )
        if cmp_remaining == 0 and move.state != "posted":
            raise ValidationError(
                _("No se permite un descuento del 100%% del subtotal de la factura.")
            )
        if move.state == "posted":
            return self._l10n_ve_action_create_credit_note(amount, remaining)
        self.env["l10n.ve.account.move.discount"].create(
            {
                "move_id": move.id,
                "reason_id": self.reason_id.id,
                "amount": amount,
                "discount_type": "percentage"
                if self.discount_mode == "percentage"
                else "fixed",
                "discount_percentage": self.discount_percentage
                if self.discount_mode == "percentage"
                else 0.0,
                "amount_base": amount_base,
            }
        )
        return {"type": "ir.actions.act_window_close"}

    def _l10n_ve_credit_note_amount_in_target_currency(self, remaining):
        self.ensure_one()
        move = self.move_id
        target = move._l10n_ve_post_discount_credit_note_currency()
        entered = self.discount_currency_id or move.currency_id
        if self.discount_mode != "amount" or entered != target:
            return None
        amount_base = self.amount_base or "untaxed"
        if amount_base == "total":
            return l10n_ve_discount_logic.l10n_ve_fixed_discount_to_untaxed(
                move,
                self.amount,
                "total",
                remaining,
                currency=entered,
            )
        return entered.round(self.amount)

    def _l10n_ve_action_create_credit_note(self, amount, remaining=None):
        self.ensure_one()
        if remaining is None:
            remaining = self.move_id._l10n_ve_discount_remaining_subtotal_by_taxes()
        credit_note = self.move_id._l10n_ve_create_post_discount_credit_note(
            amount=amount,
            reason=self.reason_id,
            amount_cn=self._l10n_ve_credit_note_amount_in_target_currency(remaining),
        )
        return {
            "type": "ir.actions.act_window",
            "name": _("Nota de crédito"),
            "res_model": "account.move",
            "view_mode": "form",
            "res_id": credit_note.id,
        }
