# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare

from odoo.addons.l10n_ve_loyalty.models import l10n_ve_global_discount as l10n_ve_discount_logic


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
    amount = fields.Monetary(string="Amount")

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if "reason_id" in fields_list and not res.get("reason_id"):
            default_reason = self.env["l10n.ve.discount.reason"]._l10n_ve_get_default()
            if default_reason:
                res["reason_id"] = default_reason.id
        return res

    def _l10n_ve_compute_percentage_discount_amount(self):
        self.ensure_one()
        move = self.move_id
        subtotal_by_taxes = move._l10n_ve_global_discount_subtotal_by_taxes()
        total_subtotal = sum(subtotal_by_taxes.values())
        return move.currency_id.round(total_subtotal * self.discount_percentage)

    def action_apply_discount(self):
        self.ensure_one()
        move = self.move_id
        move._l10n_ve_check_global_discount_allowed()
        amount_base = self.amount_base or "untaxed"
        if self.discount_mode == "percentage":
            if float_compare(self.discount_percentage, 0.0, precision_digits=10) <= 0:
                raise UserError(_("Indique el porcentaje del descuento."))
            if float_compare(self.discount_percentage, 1.0, precision_digits=10) >= 0:
                raise ValidationError(
                    _("No se permite un descuento global del 100%% en la factura.")
                )
            if move.l10n_ve_global_discount_ids.filtered(
                lambda discount: discount.discount_type == "percentage"
            ):
                raise ValidationError(_("Solo puede existir un descuento global por porcentaje."))
            amount = self._l10n_ve_compute_percentage_discount_amount()
            amount_base = "untaxed"
        else:
            if not self.amount:
                raise UserError(_("Indique el monto del descuento."))
            if amount_base == "total":
                available_total = l10n_ve_discount_logic.l10n_ve_available_total_for_discount(
                    move
                )
                cmp_total = float_compare(
                    self.amount,
                    available_total,
                    precision_digits=move.currency_id.decimal_places,
                )
                if cmp_total > 0:
                    raise ValidationError(
                        _(
                            "El descuento (%(discount)s) supera el total disponible "
                            "(%(total)s)."
                        )
                        % {"discount": self.amount, "total": available_total}
                    )
                if cmp_total == 0:
                    raise ValidationError(
                        _("No se permite un descuento del 100%% del total de la factura.")
                    )
            amount = l10n_ve_discount_logic.l10n_ve_fixed_discount_to_untaxed(
                move,
                self.amount,
                amount_base,
            )
        if float_compare(
            amount, 0.0, precision_digits=move.currency_id.decimal_places
        ) <= 0:
            raise UserError(_("El monto del descuento debe ser mayor que cero."))
        subtotal_by_taxes = move._l10n_ve_global_discount_subtotal_by_taxes()
        total_subtotal = sum(subtotal_by_taxes.values())
        already_applied = move._l10n_ve_total_sequential_global_discount(subtotal_by_taxes)
        remaining = total_subtotal - already_applied
        cmp_remaining = float_compare(
            amount,
            remaining,
            precision_digits=move.currency_id.decimal_places,
        )
        if cmp_remaining > 0:
            raise ValidationError(
                _(
                    "El descuento (%(discount)s) supera el subtotal disponible "
                    "(%(subtotal)s)."
                )
                % {"discount": amount, "subtotal": remaining}
            )
        if cmp_remaining == 0:
            raise ValidationError(
                _("No se permite un descuento del 100%% del subtotal de la factura.")
            )
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
