import logging

from odoo import Command, _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    subtotal_company_currency = fields.Monetary(
        compute="_compute_subtotal_company_currency",
        currency_field="company_currency_id",
    )

    @api.depends("balance")
    def _compute_subtotal_company_currency(self):
        for line in self:
            if line.move_id.move_type in ["out_invoice", "in_invoice"]:
                line.subtotal_company_currency = abs(line.balance)
                continue
            if line.move_id.move_type in ["out_refund", "in_refund"]:
                line.subtotal_company_currency = abs(line.balance)
                continue
            line.subtotal_company_currency = 0.0

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        for record in res:
            if record.move_id.move_type == "entry":
                continue

            if record.move_id.country_code != self.env.ref("base.ve").code:
                continue

            record._validate_price_not_zero()
            record._put_unique_tax_per_line()
        return res

    def write(self, vals):
        res = super().write(vals)
        for record in self:
            if record.move_id.move_type == "entry":
                continue
            if record.move_id.country_code != self.env.ref("base.ve").code:
                continue

            # Validar precio si se está modificando price_unit o quantity
            if "price_unit" in vals or "quantity" in vals:
                record._validate_price_not_zero()
            record._put_unique_tax_per_line()
        return res

    def _validate_price_not_zero(self):
        """Valida que las líneas de factura no tengan precio en 0"""
        self.ensure_one()
        if self.display_type not in ("product", "discount"):
            return

        if self.move_id.move_type == "entry":
            return

        # Validar que el precio unitario no sea 0
        if abs(self.price_unit or 0.0) < 0.01:
            raise ValidationError(
                _(
                    "No se permiten líneas con precio en 0. La línea '%s' tiene un precio de 0."
                )
                % (self.name or _("Sin nombre"))
            )

    def _put_unique_tax_per_line(self):
        self.ensure_one()
        if self.display_type not in ("product", "discount"):
            return

        if len(self.tax_ids) == 0:
            if self.move_id.move_type in ("out_invoice", "out_refund", "out_receipt"):
                self.tax_ids = [Command.link(self.env.company.account_sale_tax_id.id)]
                self.move_id.message_post(
                    body=_("Added default sales tax to line: %s.") % self.name
                )

            if self.move_id.move_type in ("in_invoice", "in_refund", "in_receipt"):
                self.tax_ids = [
                    Command.link(self.env.company.account_purchase_tax_id.id)
                ]
