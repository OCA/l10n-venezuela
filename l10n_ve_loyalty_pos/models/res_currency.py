# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models


class ResCurrency(models.Model):
    _inherit = "res.currency"

    @api.model
    def _load_pos_data_domain(self, data):
        domain = super()._load_pos_data_domain(data)
        config = self.env["pos.config"].browse(data["pos.config"]["data"][0]["id"])
        company = config.company_id
        is_ve = (company.country_id.code == "VE") or (
            company.account_fiscal_country_id.code == "VE"
        )
        program_currency_ids = (
            config._get_program_ids()
            .filtered(lambda program: program.program_type in ("ewallet", "gift_card"))
            .mapped("currency_id")
            .ids
        )
        # currency_pos (and similar) may already load all active currencies.
        if domain and domain[0][0] == "active":
            return domain

        currency_ids = set(program_currency_ids)
        if "payment_currency_id" in config.payment_method_ids._fields:
            currency_ids.update(config.payment_method_ids.mapped("payment_currency_id").ids)
        if company.currency_id:
            currency_ids.add(company.currency_id.id)
        if config.currency_id:
            currency_ids.add(config.currency_id.id)
        if is_ve:
            usd = self.env.ref("base.USD", raise_if_not_found=False)
            if usd and usd.active:
                currency_ids.add(usd.id)
        if domain and domain[0][0] == "id" and domain[0][1] == "=":
            currency_ids.add(domain[0][2])
        elif domain and domain[0][0] == "id" and domain[0][1] == "in":
            currency_ids.update(domain[0][2] or [])
        if not currency_ids:
            return domain
        return [("id", "in", list(currency_ids))]

    @api.model
    def _load_pos_data_fields(self, config_id):
        fields_list = super()._load_pos_data_fields(config_id)
        if "inverse_rate" not in fields_list:
            fields_list.append("inverse_rate")
        return fields_list
