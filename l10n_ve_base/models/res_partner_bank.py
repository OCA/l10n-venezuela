# Copyright 2025-Present SINAPSYS GLOBAL SA, MASTERCORE SAS
# Copyright 2026 Guillermo Montoya
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
#
# Account type adapted from l10n_ve_base 19.0 (odoo-mastercore/odoo-venezuela).

from odoo import api, fields, models


class ResPartnerBank(models.Model):
    _inherit = "res.partner.bank"

    l10n_ve_bank_country_code = fields.Char(
        related="bank_id.country.code",
        string="Bank Country Code",
    )
    l10n_ve_acc_type = fields.Selection(
        selection=[
            ("corriente", "Checking Account"),
            ("ahorro", "Savings Account"),
            ("fideicomiso", "Trust Account"),
        ],
        string="Account Type",
    )

    @api.onchange("bank_id")
    def _onchange_bank_id_ve(self):
        bank = self.bank_id
        if (
            bank
            and bank.country
            and bank.country.code == "VE"
            and bank.bic
            and not (self.acc_number or "").strip()
        ):
            self.acc_number = bank.bic
