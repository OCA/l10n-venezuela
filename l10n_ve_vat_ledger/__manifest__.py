###############################################################################
# Author: SINAPSYS GLOBAL SA || MASTERCORE SAS
# Copyleft: 2020-Present.
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).
#
#
###############################################################################
{
    "name": "Localización Vat Ledger Venezuela",
    "author": "SINAPSYS GLOBAL SA, MASTERCORE SAS, Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/l10n-venezuela",
    "version": "15.0.8",
    "category": "Localization",
    "license": "AGPL-3",
    "depends": ["account", "l10n_ve_base", "l10n_ve_withholding", "report_xlsx"],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "views/account_vat_ledger_views.xml",
        "wizard/account_wizard_views.xml",
        "report/account_vat_ledger_report.xml",
    ],
}
