# Copyright 2011-2016 Vauxoo
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

{
    "name": "Fiscal Report For Venezuela (Libros Fiscales)",
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
        "l10n_ve_withholding_iva",
    ],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "reports/report_fiscal_book.xml",
        "wizards/wizard_fiscal_book_views.xml",
        "views/fiscal_book_views.xml",
        "views/menu_views.xml",
    ],
    "installable": True,
    "auto_install": False,
    "application": False,
}
