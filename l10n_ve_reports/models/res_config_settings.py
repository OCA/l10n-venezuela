# Part of Odoo. See LICENSE file for full copyright and licensing details.


from odoo import models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    def open_tax_group_list(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Tax groups",
            "res_model": "account.tax.group",
            "view_mode": "list",
            "context": {
                "default_country_id": self.account_fiscal_country_id.id,
                "search_default_country_id": self.account_fiscal_country_id.id,
            },
        }
