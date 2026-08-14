# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare


class L10nVeAccountMovePostDiscountWizard(models.TransientModel):
    _name = "l10n.ve.account.move.post.discount.wizard"
    _description = "Venezuela post-invoice discount credit note wizard"

    move_id = fields.Many2one(
        comodel_name="account.move",
        string="Invoice",
        required=True,
        readonly=True,
    )
    company_id = fields.Many2one(related="move_id.company_id")
    currency_id = fields.Many2one(related="move_id.currency_id")
    available_untaxed_amount = fields.Monetary(
        string="Subtotal disponible",
        currency_field="currency_id",
        readonly=True,
    )
    discount_mode = fields.Selection(
        selection=[
            ("percentage", "Porcentaje"),
            ("amount", "Monto fijo"),
        ],
        string="Tipo de descuento",
        default="percentage",
        required=True,
    )
    reason_id = fields.Many2one(
        comodel_name="l10n.ve.discount.reason",
        string="Motivo de descuento",
        required=True,
    )
    discount_percentage = fields.Float(string="Porcentaje")
    amount = fields.Monetary(string="Monto", currency_field="currency_id")

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        move = self.env["account.move"]
        if res.get("move_id"):
            move = self.env["account.move"].browse(res["move_id"])
        elif self.env.context.get("active_model") == "account.move" and self.env.context.get(
            "active_id"
        ):
            move = self.env["account.move"].browse(self.env.context["active_id"])
            res["move_id"] = move.id
        if move:
            if "available_untaxed_amount" in fields_list:
                res["available_untaxed_amount"] = (
                    move._l10n_ve_post_discount_available_untaxed()
                )
            if "reason_id" in fields_list and not res.get("reason_id"):
                default_reason = self.env["l10n.ve.discount.reason"]._l10n_ve_get_default()
                if default_reason:
                    res["reason_id"] = default_reason.id
        return res

    def _l10n_ve_compute_discount_amount(self):
        self.ensure_one()
        move = self.move_id
        if self.discount_mode == "percentage":
            if float_compare(self.discount_percentage, 0.0, precision_digits=10) <= 0:
                raise UserError(_("Indique el porcentaje del descuento."))
            if float_compare(self.discount_percentage, 1.0, precision_digits=10) > 0:
                raise ValidationError(
                    _("El porcentaje de descuento no puede ser mayor al 100%%.")
                )
            return move.currency_id.round(move.amount_untaxed * self.discount_percentage)
        if not self.amount:
            raise UserError(_("Indique el monto del descuento."))
        return self.amount

    def action_create_credit_note(self):
        self.ensure_one()
        move = self.move_id
        move._l10n_ve_check_post_discount_allowed()
        amount = self._l10n_ve_compute_discount_amount()
        available = move._l10n_ve_post_discount_available_untaxed()
        if float_compare(
            amount, 0.0, precision_digits=move.currency_id.decimal_places
        ) <= 0:
            raise UserError(_("El monto del descuento debe ser mayor que cero."))
        if float_compare(
            amount, available, precision_digits=move.currency_id.decimal_places
        ) > 0:
            raise ValidationError(
                _(
                    "El descuento (%(discount)s) supera el subtotal disponible "
                    "(%(subtotal)s)."
                )
                % {"discount": amount, "subtotal": available}
            )
        credit_note = move._l10n_ve_create_post_discount_credit_note(
            amount=amount,
            reason=self.reason_id,
        )
        return {
            "type": "ir.actions.act_window",
            "name": _("Nota de crédito"),
            "res_model": "account.move",
            "view_mode": "form",
            "res_id": credit_note.id,
        }
