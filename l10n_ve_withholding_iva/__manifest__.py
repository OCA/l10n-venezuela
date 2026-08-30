# Copyright 2011-2016 Vauxoo
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

{
    "name": "Management Withholding VAT Venezuelan Laws",
    "version": "14.0.1.0.0",
    "category": "Localization",
    "author": "Vauxoo, Odoo Community Association (OCA)",
    "maintainer": "Orlov Solutions LLC",
    "maintainers": [
        "xavikveg",  # Xavier Orlov
        "guillermm",  # Guillermo Montoya
    ],
    "website": "https://github.com/OCA/l10n-venezuela",
    "license": "AGPL-3",
    "depends": [
        "account",
        "l10n_ve_fiscal_requirements",
        "l10n_ve_withholding",
    ],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "data/ir_sequence_data.xml",
        "reports/report_wh_iva.xml",
        "wizards/generate_txt_views.xml",
        "views/wh_iva_views.xml",
        "views/account_move_views.xml",
        "views/res_company_views.xml",
        "views/menu_views.xml",
    ],
    "installable": True,
    "auto_install": False,
    "application": False,
}
