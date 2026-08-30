# Copyright 2011-2016 Vauxoo
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

{
    "name": "VAT Write Off (Ajustes de Crédito Fiscal)",
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
        "l10n_ve_fiscal_book",
    ],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "views/vat_write_off_views.xml",
    ],
    "installable": True,
    "auto_install": False,
    "application": False,
}
