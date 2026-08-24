# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare

from odoo.addons.l10n_ve_loyalty.models import (
    l10n_ve_global_discount as l10n_ve_discount_logic,
)


class L10nVeSaleOrderDiscount(models.Model):
    _name = "l10n.ve.sale.order.discount"
    _inherit = ["l10n.ve.global.discount.mixin"]
    _description = "Venezuela sale order global discount"
    _order = "id"

    sale_order_id = fields.Many2one(
        comodel_name="sale.order",
        string="Sale Order",
        required=True,
        ondelete="cascade",
        index=True,
    )
    reason_id = fields.Many2one(
        comodel_name="l10n.ve.discount.reason",
        string="Reason",
        required=True,
        ondelete="restrict",
        default=lambda self: self.env["l10n.ve.discount.reason"]._l10n_ve_get_default(),
    )
    name = fields.Char(related="reason_id.name", readonly=True)
    amount = fields.Monetary(
        required=True,
        currency_field="currency_id",
    )
    currency_id = fields.Many2one(
        related="sale_order_id.currency_id",
        store=True,
        readonly=True,
    )
    company_id = fields.Many2one(
        related="sale_order_id.company_id",
        store=True,
        readonly=True,
    )
    amount_invoiced = fields.Monetary(
        string="Invoiced Amount",
        compute="_compute_amount_invoiced",
        store=True,
        currency_field="currency_id",
    )
    invoice_discount_ids = fields.One2many(
        comodel_name="l10n.ve.account.move.discount",
        inverse_name="l10n_ve_sale_discount_id",
        string="Invoice discounts",
    )

    @api.depends(
        "amount",
        "invoice_discount_ids.amount",
        "invoice_discount_ids.move_id.state",
    )
    def _compute_amount_invoiced(self):
        for discount in self:
            discount.amount_invoiced = sum(
                invoice_discount.amount
                for invoice_discount in discount.invoice_discount_ids
                if invoice_discount.move_id.state != "cancel"
            )

    @api.constrains("amount")
    def _check_amount_positive(self):
        for discount in self:
            if (
                float_compare(
                    discount.amount,
                    0.0,
                    precision_digits=discount.currency_id.decimal_places,
                )
                <= 0
            ):
                raise ValidationError(
                    _("El monto del descuento debe ser mayor que cero.")
                )

    @api.constrains("discount_type", "sale_order_id")
    def _check_single_percentage_discount(self):
        for discount in self.filtered(
            lambda record: record.discount_type == "percentage"
        ):
            others = discount.sale_order_id.l10n_ve_global_discount_ids.filtered(
                lambda record, current=discount: (
                    record.discount_type == "percentage" and record.id != current.id
                )
            )
            if others:
                raise ValidationError(
                    _("Solo puede existir un descuento global por porcentaje.")
                )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        if not self.env.context.get("l10n_ve_skip_discount_refresh"):
            records._l10n_ve_check_order_editable()
            records.sale_order_id._l10n_ve_check_single_percentage_global_discount(
                records.sale_order_id.l10n_ve_global_discount_ids
            )
            l10n_ve_discount_logic.l10n_ve_refresh_percentage_global_discount_amounts(
                records.sale_order_id
            )
            l10n_ve_discount_logic.l10n_ve_validate_global_discount_total(
                records.sale_order_id
            )
        return records

    def write(self, vals):
        res = super().write(vals)
        if self.env.context.get("l10n_ve_skip_discount_refresh"):
            return res
        if {"reason_id", "amount", "discount_type", "discount_percentage"} & set(vals):
            self._l10n_ve_check_order_editable()
            self.sale_order_id._l10n_ve_check_single_percentage_global_discount(
                self.sale_order_id.l10n_ve_global_discount_ids
            )
            l10n_ve_discount_logic.l10n_ve_refresh_percentage_global_discount_amounts(
                self.sale_order_id
            )
            l10n_ve_discount_logic.l10n_ve_validate_global_discount_total(
                self.sale_order_id
            )
        return res

    def unlink(self):
        self._l10n_ve_check_order_editable()
        if any(discount.amount_invoiced for discount in self):
            raise UserError(
                _("No puede eliminar un descuento global que ya fue facturado.")
            )
        return super().unlink()

    def _l10n_ve_check_order_editable(self):
        for discount in self:
            order = discount.sale_order_id
            if order.country_code != "VE":
                raise UserError(
                    _("Los descuentos globales venezolanos solo aplican a pedidos VE.")
                )
            if order.state == "cancel":
                raise UserError(
                    _("No puede modificar descuentos en pedidos cancelados.")
                )
            if order.state == "sale" and discount.amount_invoiced:
                raise UserError(
                    _(
                        "No puede modificar un descuento global "
                        "parcialmente facturado. "
                        "Ajuste las facturas en borrador o cree un nuevo "
                        "descuento."
                    )
                )
