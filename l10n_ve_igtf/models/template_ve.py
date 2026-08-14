from odoo import models

from odoo.addons.account.models.chart_template import template

_L10N_VE_IGTF_ACCOUNT_VALUES = {
    "name": "IMPUESTOS DE GRANDES TRANSACCIONES FINANCIERAS (IGTF)",
    "code": "2102003",
    "account_type": "liability_current",
    "reconcile": True,
}


class AccountChartTemplate(models.AbstractModel):
    _inherit = "account.chart.template"

    @template("ve_seniat", "res.company")
    def _get_ve_seniat_res_company_igtf(self):
        return {
            self.env.company.id: {
                "l10n_ve_igtf_account_id": "l10n_ve_seniat.account_account_2102003",
                "l10n_ve_igtf_percent": 3.0,
            },
        }

    @template("ve_seniat_basic", "account.account")
    def _get_ve_seniat_basic_igtf_account(self):
        return {
            "l10n_ve_igtf.l10n_ve_igtf_account_igtf_payable": _L10N_VE_IGTF_ACCOUNT_VALUES,
        }

    @template("ve_seniat_basic", "res.company")
    def _get_ve_seniat_basic_res_company_igtf(self):
        return {
            self.env.company.id: {
                "l10n_ve_igtf_account_id": "l10n_ve_igtf.l10n_ve_igtf_account_igtf_payable",
                "l10n_ve_igtf_percent": 3.0,
            },
        }

    @template("ve_seniat_empty", "account.account")
    def _get_ve_seniat_empty_igtf_account(self):
        return {
            "l10n_ve_igtf.l10n_ve_igtf_account_igtf_payable": _L10N_VE_IGTF_ACCOUNT_VALUES,
        }

    @template("ve_seniat_empty", "res.company")
    def _get_ve_seniat_empty_res_company_igtf(self):
        return {
            self.env.company.id: {
                "l10n_ve_igtf_account_id": "l10n_ve_igtf.l10n_ve_igtf_account_igtf_payable",
                "l10n_ve_igtf_percent": 3.0,
            },
        }
