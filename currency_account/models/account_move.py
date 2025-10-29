from odoo import api, fields, models
import json

import logging

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"

    total_currencies = fields.Json(
        string="Totales por Moneda",
        compute="_compute_total_currencies",
        store=True,
        help="Almacena el total de la factura y el residuo pendiente en cada moneda habilitada.",
    )

    @api.depends(
        "line_ids.price_subtotal",
        "line_ids.tax_ids",
        "line_ids.price_total",
        "currency_id",
        "amount_total",
        "amount_residual",
        "company_id.currency_id",
    )
    def _compute_total_currencies(self):
        for move in self:
            totals = {}
            company_currency = move.company_id.currency_id

            currencies = self.env["res.currency"].search([("active", "=", True), ("id", "!=", move.currency_id.id)])

            for currency in currencies:
                date = move.date or fields.Date.today()
                total_in_currency = move.currency_id._convert(move.amount_total, currency, move.company_id, date)

                if currency == company_currency:
                    date = fields.Date.today()

                residual_in_currency = move.currency_id._convert(move.amount_residual, currency, move.company_id, date)

                totals[str(currency.id)] = {
                    "currency_id": currency.id,
                    "currency_name": currency.name,
                    "total": total_in_currency,
                    "residual": residual_in_currency,
                }

            # El campo JSON debe almacenar una estructura serializable
            move.total_currencies = json.dumps(totals) if totals else False
