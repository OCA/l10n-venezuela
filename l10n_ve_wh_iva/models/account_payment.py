# Copyright 2026 BWEALTHICS LLC
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import fields, models


class AccountPayment(models.Model):
    _inherit = "account.payment"

    l10n_ve_iva_wh_received_amount = fields.Monetary(
        string="IVA Retenido por el Cliente",
        currency_field="currency_id",
        copy=False,
        help="Monto de IVA retenido por el cliente (agente de retención) sobre "
        "este cobro, según el comprobante recibido. Los libros fiscales lo "
        "usan para reportar la retención recibida por factura.",
    )
    l10n_ve_iva_wh_received_number = fields.Char(
        string="Nº de Comprobante de Retención Recibido",
        size=14,
        copy=False,
        help="Numeración de 14 caracteres del comprobante de retención "
        "entregado por el cliente: AAAAMM + secuencial de 8 dígitos.",
    )
