# Copyright 2011-2016 Vauxoo
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

{
    "name": "Split Invoices for Venezuela",
    "version": "14.0.1.0.0",
    "category": "Localization",
    "author": "Vauxoo",
        "maintainer": "Orlov Solutions LLC",
    "maintainers": [
        "xavikveg",  # Xavier Orlov
        "guillermm",  # Guillermo Montoya
    ],
    "website": "http://vauxoo.com",
    "license": "AGPL-3",
    "depends": [
        "account",
        "l10n_ve_fiscal_requirements",
    ],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
    ],
    "installable": True,
    "auto_install": False,
    "application": False,
}
