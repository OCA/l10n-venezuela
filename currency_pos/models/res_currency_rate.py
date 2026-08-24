from odoo import api, fields, models


class ResCurrencyRate(models.Model):
    _name = "res.currency.rate"
    _inherit = ["res.currency.rate", "pos.load.mixin"]

    @api.model
    def _load_pos_data_domain(self, data):
        currencies_data = data.get("res.currency", {}).get("data", [])
        if not currencies_data:
            return [("id", "=", False)]

        currency_ids = [c["id"] for c in currencies_data]
        config_data = data.get("pos.config", {}).get("data", [])
        if config_data:
            company = self.env["res.company"].browse(config_data[0]["company_id"])
            company_currency_id = company.currency_id.id
            if company_currency_id:
                currency_ids = [cid for cid in currency_ids if cid != company_currency_id]

        today = fields.Date.today()
        return [
            ("currency_id", "in", currency_ids),
            ("name", "<=", today),
        ]

    @api.model
    def _load_pos_data_fields(self, config_id):
        return ["id", "currency_id", "name", "rate", "company_id"]

    @api.model
    def _load_pos_data(self, data):
        domain = self._load_pos_data_domain(data)
        if domain == [("id", "=", False)]:
            return {"data": [], "fields": self._load_pos_data_fields(data["pos.config"]["data"][0]["id"])}

        fields_list = self._load_pos_data_fields(data["pos.config"]["data"][0]["id"])
        rates = self.search_read(domain, fields_list, order="currency_id, name desc", load=False)

        currency_rates = {}
        for rate in rates:
            currency_id = rate["currency_id"][0] if isinstance(rate["currency_id"], list) else rate["currency_id"]

            if currency_id not in currency_rates:
                currency_rates[currency_id] = rate
            else:
                existing_date = fields.Date.from_string(currency_rates[currency_id]["name"])
                current_date = fields.Date.from_string(rate["name"])
                if current_date > existing_date:
                    currency_rates[currency_id] = rate

        return {
            "data": list(currency_rates.values()),
            "fields": fields_list,
        }
