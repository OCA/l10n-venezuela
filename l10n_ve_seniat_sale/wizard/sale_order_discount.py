# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, models
from odoo.exceptions import ValidationError
from odoo.tools.float_utils import float_compare


class SaleOrderDiscount(models.TransientModel):
    _inherit = "sale.order.discount"

    def _l10n_ve_check_discount_percentage(self):
        for wizard in self:
            order = wizard.sale_order_id
            if not order or order.country_code != "VE":
                continue
            if wizard.discount_type not in ("sol_discount", "so_discount"):
                continue
            prec = self.env["decimal.precision"].precision_get("Discount")
            percent = (wizard.discount_percentage or 0.0) * 100.0
            if float_compare(percent, 100.0, precision_digits=prec) >= 0:
                raise ValidationError(
                    _("No se permite un descuento global del 100%% en el pedido.")
                )

    def action_apply_discount(self):
        self._l10n_ve_check_discount_percentage()
        return super().action_apply_discount()
