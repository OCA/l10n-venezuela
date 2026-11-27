# Copyright 2026 Guillermo Montoya
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import models

from odoo.addons.account.models.chart_template import template


class AccountChartTemplate(models.AbstractModel):
    _inherit = "account.chart.template"

    @template("ve", "res.company")
    def _get_ve_res_company(self):
        """Default sale/purchase tax is IVA 16% (tax1), not the additional aliquot.

        Official l10n_ve 19.0 still sets tax3 (22%, rewritten here to 31%).
        tax1 is the general rate (12%, rewritten here to 16%).
        """
        data = super()._get_ve_res_company()
        for vals in data.values():
            vals["account_sale_tax_id"] = "tax1sale"
            vals["account_purchase_tax_id"] = "tax1purchase"
        return data
