# Copyright 2011-2016 Vauxoo
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

{
    "name": "ISLR Sale and Purchase Functionalities",
    "version": "14.0.1.0.0",
    "category": "Localization",
    "author": "Vauxoo",
        "maintainer": "Orlov Solutions LLC",
    "maintainers": [
        "xavikveg",  # Xavier Orlov
        "guillermm",  # Guillermo Montoya
    ],
    "website": "https://www.odoo.com",
    "license": "AGPL-3",
    "depends": [
        "sale_management",
        "purchase",
        "l10n_ve_withholding_islr",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/sale_order_views.xml",
        "views/purchase_order_views.xml",
    ],
    "installable": True,
    "auto_install": False,
    "application": False,
}
