from odoo import api, models
from odoo.tools import float_round


class ResCurrency(models.Model):
    _inherit = "res.currency"

    @api.model
    def get_exchange_rates(self):
        company_currency = self.env.company.currency_id
        currencies = self.env["res.currency"].search([("active", "=", True), ("id", "!=", company_currency.id)])

        rates_data = []
        for currency in currencies:
            rates_data.append(
                {
                    "name": currency.name,
                    "symbol": currency.symbol,
                    "rate": float_round(currency.inverse_rate, precision_digits=currency.decimal_places),
                    "company_currency_name": company_currency.name,
                    "company_currency_symbol": company_currency.symbol,
                }
            )

        return {
            "company_currency": company_currency.name,
            "rates": rates_data,
        }
