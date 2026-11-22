# Copyright 2026 BWEALTHICS LLC
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

import re

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

RECEIVED_VOUCHER_RE = re.compile(r"^\d{4}(0[1-9]|1[0-2])\d{8}$")


class AccountPaymentRegister(models.TransientModel):
    _inherit = "account.payment.register"

    l10n_ve_iva_wh_received_amount = fields.Monetary(
        string="IVA Retenido por el Cliente",
        currency_field="currency_id",
        default=0.0,
        help="Monto de IVA que el cliente (agente de retención) retuvo según "
        "el comprobante entregado. Se descuenta del cobro y se registra "
        "en la cuenta de Retenciones de IVA Recibidas de Clientes.",
    )
    l10n_ve_iva_wh_voucher_number = fields.Char(
        string="Número de Comprobante Recibido",
        size=14,
        help="Numeración de 14 caracteres del comprobante de retención del "
        "cliente: AAAAMM + secuencial de 8 dígitos.",
    )

    @api.constrains("l10n_ve_iva_wh_voucher_number")
    def _check_l10n_ve_iva_wh_voucher_number(self):
        for wizard in self:
            number = wizard.l10n_ve_iva_wh_voucher_number
            if number and not RECEIVED_VOUCHER_RE.match(number):
                raise ValidationError(
                    self.env._(
                        "El número de comprobante de retención debe tener 14 "
                        "dígitos: AAAAMM + secuencial de 8 dígitos "
                        "(ej. 20260700000001)."
                    )
                )

    def _l10n_ve_iva_wh_get_values(self):
        """Return validated received-withholding values without side effects.

        The withholding practiced by the company as agent is issued when the
        vendor bill is posted (see account.move), so the payment only settles
        the remaining net amount.
        """
        self.ensure_one()
        received = self.l10n_ve_iva_wh_received_amount
        if not (
            self.payment_type == "inbound"
            and self.partner_type == "customer"
            and received
        ):
            return {}

        edit_mode = self.can_edit_wizard and (
            len(self.batches[0]["lines"]) == 1 or self.group_payment
        )
        if not edit_mode:
            raise UserError(
                self.env._(
                    "Para aplicar retención de IVA registre un solo pago agrupado "
                    "(active «Agrupar pagos» o pague las facturas una a una)."
                )
            )
        if self.is_register_payment_on_draft:
            raise UserError(
                self.env._(
                    "No se puede aplicar retención de IVA sobre documentos en "
                    "borrador: publique las facturas antes de registrar el pago."
                )
            )
        if received < 0:
            raise UserError(
                self.env._("El IVA retenido por el cliente no puede ser negativo.")
            )
        if not self.l10n_ve_iva_wh_voucher_number:
            raise UserError(
                self.env._(
                    "Indique el número del comprobante de retención recibido "
                    "(14 dígitos: AAAAMM + 8)."
                )
            )
        account = self.company_id.l10n_ve_iva_wh_received_account_id
        if not account:
            raise UserError(
                self.env._(
                    "Configure la cuenta de Retenciones de IVA Recibidas de "
                    "Clientes en Ajustes > Contabilidad > Localización Venezuela."
                )
            )
        withholding = self.currency_id.round(received)
        if self.currency_id.compare_amounts(withholding, self.amount) >= 0:
            raise UserError(
                self.env._(
                    "La retención de IVA (%(wh)s) no puede ser mayor o igual al "
                    "monto del pago (%(amount)s).",
                    wh=withholding,
                    amount=self.amount,
                )
            )
        if self.currency_id.is_zero(withholding):
            return {}
        return {
            "wh": withholding,
            "account": account,
            "label": self.env._(
                "Ret. IVA recibida comprobante %s",
                self.l10n_ve_iva_wh_voucher_number,
            ),
        }

    def _create_payment_vals_from_wizard(self, batch_result):
        """Add a dedicated withholding write-off line to the payment."""
        payment_vals = super()._create_payment_vals_from_wizard(batch_result)
        wh_values = self._l10n_ve_iva_wh_get_values()
        if not wh_values:
            return payment_vals
        withholding = wh_values["wh"]
        payment_vals["amount"] -= withholding
        payment_vals.setdefault("write_off_line_vals", []).append(
            {
                "name": wh_values["label"],
                "account_id": wh_values["account"].id,
                "partner_id": self.partner_id.commercial_partner_id.id,
                "currency_id": self.currency_id.id,
                "amount_currency": withholding,
                "balance": self.currency_id._convert(
                    withholding,
                    self.company_id.currency_id,
                    self.company_id,
                    self.payment_date,
                ),
            }
        )
        payment_vals["l10n_ve_iva_wh_received_amount"] = withholding
        payment_vals["l10n_ve_iva_wh_received_number"] = (
            self.l10n_ve_iva_wh_voucher_number
        )
        return payment_vals
