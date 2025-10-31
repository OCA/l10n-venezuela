from odoo import api, fields, models, _
from odoo.addons.account.models.chart_template import template


import logging

_logger = logging.getLogger(__name__)


class AccountChartTemplate(models.AbstractModel):
    _inherit = "account.chart.template"

    def _post_load_data(self, template_code, company, template_data):
        res = super()._post_load_data(template_code, company, template_data)
        company = company or self.env.company
        if template_code == "ve_seniat":
            company.iva_supplier_retention_journal_id = self.ref("rip", raise_if_not_found=False)
            company.iva_customer_retention_journal_id = self.ref("ric", raise_if_not_found=False)
            company.islr_supplier_retention_journal_id = self.ref("islrp", raise_if_not_found=False)
            company.islr_customer_retention_journal_id = self.ref("islrc", raise_if_not_found=False)

        return res

    @template(model="account.journal")
    def _get_account_journal(self, template_code):
        vals = super()._get_account_journal(template_code)
        vals["rip"] = {
            "name": _("Retenciones IVA Proveedores"),
            "type": "bank",
            "code": _("RIP"),
            "show_on_dashboard": False,
            "sequence": 9,
        }
        vals["ric"] = {
            "name": _("Retenciones IVA Clientes"),
            "type": "bank",
            "code": _("RIC"),
            "show_on_dashboard": False,
            "sequence": 9,
        }
        vals["islrp"] = {
            "name": _("Retencion de ISLR de proveedores"),
            "type": "bank",
            "code": _("ISLRP"),
            "show_on_dashboard": False,
            "sequence": 9,
        }
        vals["islrc"] = {
            "name": _("Retencion de ISLR de Clientes"),
            "type": "bank",
            "code": _("ISLRC"),
            "show_on_dashboard": False,
            "sequence": 9,
        }

        if template_code == "ve_seniat":
            # Retencion de ISLR de Proveedores
            vals["rip"]["default_account_id"] = "account_activa_account_2172004"
            vals["rip"]["suspense_account_id"] = "account_activa_account_9999909"
            # Retencion de ISLR de Clientes
            vals["ric"]["default_account_id"] = "account_activa_account_1151003"
            vals["ric"]["suspense_account_id"] = "account_activa_account_9999909"
            # Retencion de ISLR de Proveedores
            vals["islrp"]["default_account_id"] = "account_activa_account_2172002"
            vals["islrp"]["suspense_account_id"] = "account_activa_account_9999909"
            ## Adjust sequenc
            vals["islrc"]["default_account_id"] = "account_activa_account_1151002"
            vals["islrc"]["suspense_account_id"] = "account_activa_account_9999909"

        return vals
