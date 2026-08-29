# Copyright 2011-2016 Vauxoo
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

{
    "name": "Venezuelan Fiscal Requirements",
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
        "base_vat",
    ],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "data/l10n_ut_data.xml",
        "data/seniat_url_data.xml",
        "views/l10n_ut_views.xml",
        "views/seniat_url_views.xml",
        "views/res_partner_views.xml",
        "views/res_company_views.xml",
        "views/account_tax_views.xml",
        "views/account_move_views.xml",
        "views/wizards_views.xml",
        "views/menu_views.xml",
    ],
    "installable": True,
    "auto_install": False,
    "application": False,
}
