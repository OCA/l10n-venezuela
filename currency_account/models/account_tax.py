from odoo import models, fields, api, _

class AccountTax(models.Model):
    _inherit = 'account.tax'

    @api.model
    def _prepare_base_line_grouping_key(self, base_line):
        res = super()._prepare_base_line_grouping_key(base_line)
        res["price_subtotal_currency"] = base_line["price_subtotal_currency"]
        return res


    @api.model
    def _prepare_base_line_for_taxes_computation(self, record, **kwargs):
        def load(field, fallback, from_base_line=False):
            return self._get_base_line_field_value_from_record(record, field, kwargs, fallback, from_base_line=from_base_line)

        res = super()._prepare_base_line_for_taxes_computation(record, **kwargs)
        res["price_subtotal_currency"] = load("price_subtotal_currency", 0.0)
        return res