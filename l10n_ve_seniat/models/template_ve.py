# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import _, models

from odoo.addons.account.models.chart_template import template


class AccountChartTemplate(models.AbstractModel):
    _inherit = "account.chart.template"

    @template("ve_seniat")
    def _get_ve_seniat_template_data(self):
        return {
            "code_digits": "7",
            "property_account_receivable_id": "account_account_1106001",
            "property_account_payable_id": "account_account_2101002",
            "property_account_expense_categ_id": "account_account_5101001",
            "property_account_income_categ_id": "account_account_4101001",
            "name": _("SENIAT"),
        }

    @template("ve_seniat", "res.company")
    def _get_ve_seniat_res_company(self):
        return {
            self.env.company.id: {
                "account_fiscal_country_id": "base.ve",
                "cash_account_code_prefix": "1101",
                "bank_account_code_prefix": "1102",
                "income_currency_exchange_account_id": "account_account_4102004",  # noqa: E501
                "expense_currency_exchange_account_id": "account_account_5102014",  # noqa: E501
                "tax_calculation_rounding_method": "round_globally",
                "account_sale_tax_id": "tax0sale",
                "account_purchase_tax_id": "tax0purchase",
                "exent_aliquot_sale": "tax0sale",
                "general_aliquot_sale": "tax1sale",
                "reduced_aliquot_sale": "tax2sale",
                "extend_aliquot_sale": "tax3sale",
                "exent_aliquot_purchase": "tax0purchase",
                "general_aliquot_purchase": "tax1purchase",
                "reduced_aliquot_purchase": "tax2purchase",
                "extend_aliquot_purchase": "tax3purchase",
            },
        }
