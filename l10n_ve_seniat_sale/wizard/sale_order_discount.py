# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import float_compare

from odoo.addons.l10n_ve_loyalty.models import l10n_ve_global_discount as l10n_ve_discount_logic


class SaleOrderDiscount(models.TransientModel):
    _inherit = "sale.order.discount"

    l10n_ve_discount_reason_id = fields.Many2one(
        comodel_name="l10n.ve.discount.reason",
        string="Razón de descuento",
        required=True,
    )
    l10n_ve_discount_mode = fields.Selection(
        selection=[
            ("percentage", "Porcentaje"),
            ("amount", "Monto fijo"),
        ],
        string="Tipo de descuento",
        default="percentage",
    )
    l10n_ve_amount_base = fields.Selection(
        selection=[
            ("untaxed", "Subtotal"),
            ("total", "Total"),
        ],
        string="Base del monto",
        default="untaxed",
        help="Indica si el monto fijo se toma del subtotal o del total con impuestos.",
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if "l10n_ve_discount_reason_id" in fields_list and not res.get(
            "l10n_ve_discount_reason_id"
        ):
            default_reason = self.env["l10n.ve.discount.reason"]._l10n_ve_get_default()
            if default_reason:
                res["l10n_ve_discount_reason_id"] = default_reason.id
        return res

    def _l10n_ve_compute_global_discount_amount(self):
        self.ensure_one()
        order = self.sale_order_id
        if self.l10n_ve_discount_mode == "amount":
            if float_compare(
                self.discount_amount,
                0.0,
                precision_digits=order.currency_id.decimal_places,
            ) <= 0:
                return 0.0
            return l10n_ve_discount_logic.l10n_ve_fixed_discount_to_untaxed(
                order,
                self.discount_amount,
                self.l10n_ve_amount_base or "untaxed",
            )

        discount_percentage = self.discount_percentage
        total_discount = 0.0
        for line in order.order_line:
            if not line.product_uom_qty or not line.price_unit:
                continue
            if line.display_type or line.is_downpayment:
                continue
            disc_product = order.company_id.sale_discount_product_id
            if disc_product and line.product_id == disc_product:
                continue
            taxes = line.tax_id.flatten_taxes_hierarchy()
            taxes -= taxes.filtered(lambda tax: tax.amount_type == "fixed")
            line_base = line.price_unit * (1 - (line.discount or 0.0) / 100) * line.product_uom_qty
            total_discount += line_base * discount_percentage
        return total_discount

    def _l10n_ve_apply_ve_global_discount(self):
        self.ensure_one()
        self = self.with_company(self.company_id)
        order = self.sale_order_id
        amount = self._l10n_ve_compute_global_discount_amount()
        if float_compare(
            amount, 0.0, precision_digits=order.currency_id.decimal_places
        ) <= 0:
            return
        self.env["l10n.ve.sale.order.discount"].create(
            {
                "sale_order_id": order.id,
                "reason_id": self.l10n_ve_discount_reason_id.id,
                "amount": amount,
                "discount_type": "percentage"
                if self.l10n_ve_discount_mode == "percentage"
                else "fixed",
                "discount_percentage": self.discount_percentage
                if self.l10n_ve_discount_mode == "percentage"
                else 0.0,
                "amount_base": self.l10n_ve_amount_base
                if self.l10n_ve_discount_mode == "amount"
                else "untaxed",
            }
        )

    def action_apply_discount(self):
        self.ensure_one()
        if self.company_id.account_fiscal_country_id.code == "VE":
            order = self.sale_order_id
            if not self.l10n_ve_discount_reason_id:
                raise ValidationError(_("Seleccione la razón del descuento."))
            if self.l10n_ve_discount_mode == "percentage":
                if float_compare(self.discount_percentage, 0.0, precision_digits=10) <= 0:
                    raise ValidationError(_("Indique el porcentaje del descuento."))
                if float_compare(self.discount_percentage, 1.0, precision_digits=10) >= 0:
                    raise ValidationError(
                        _("No se permite un descuento global del 100%% en el pedido.")
                    )
                if order.l10n_ve_global_discount_ids.filtered(
                    lambda discount: discount.discount_type == "percentage"
                ):
                    raise ValidationError(_("Solo puede existir un descuento global por porcentaje."))
            else:
                if float_compare(
                    self.discount_amount,
                    0.0,
                    precision_digits=self.currency_id.decimal_places,
                ) <= 0:
                    raise ValidationError(_("Indique el monto del descuento."))
                amount_base = self.l10n_ve_amount_base or "untaxed"
                if amount_base == "total":
                    available = l10n_ve_discount_logic.l10n_ve_available_total_for_discount(
                        order
                    )
                    if float_compare(
                        self.discount_amount,
                        available,
                        precision_digits=self.currency_id.decimal_places,
                    ) >= 0:
                        raise ValidationError(
                            _("No se permite un descuento del 100%% del importe del pedido.")
                        )
                else:
                    so_amount = order.amount_untaxed
                    remaining = dict(
                        l10n_ve_discount_logic.l10n_ve_remaining_subtotal_by_taxes(order)
                    )
                    so_amount = sum(remaining.values()) or so_amount
                    if so_amount and float_compare(
                        self.discount_amount,
                        so_amount,
                        precision_digits=self.currency_id.decimal_places,
                    ) >= 0:
                        raise ValidationError(
                            _("No se permite un descuento del 100%% del importe del pedido.")
                        )
            self._l10n_ve_apply_ve_global_discount()
            return
        return super().action_apply_discount()

    def _prepare_discount_product_values(self):
        vals = super()._prepare_discount_product_values()
        company = self.company_id
        if company.account_fiscal_country_id.code != "VE":
            return vals
        sale_tax = company.account_sale_tax_id
        purchase_tax = company.account_purchase_tax_id
        if sale_tax:
            vals["taxes_id"] = [(6, 0, [sale_tax.id])]
        if purchase_tax:
            vals["supplier_taxes_id"] = [(6, 0, [purchase_tax.id])]
        return vals
