# Copyright 2011-2016 Vauxoo
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

{
    "name": "Local Withholding Venezuelan Laws (Municipal Withholdings)",
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
        "views/wh_muni_views.xml",
        "views/menu_views.xml",
    ],
    "installable": True,
    "auto_install": False,
    "application": False,
}
