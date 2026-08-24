# Copyright 2026 andyengit
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

{
    "name": "Multicurrency Accounting",
    "summary": "Company-currency totals and multi-currency helpers on invoices",
    "version": "18.0.1.0.1",
    "development_status": "Beta",
    "category": "Accounting",
    "countries": ["ve"],
    "author": "andyengit, Odoo Community Association (OCA)",
    "maintainers": ["andyengit"],
    "website": "https://github.com/OCA/l10n-venezuela",
    "license": "LGPL-3",
    "depends": ["account", "product"],
    "data": [
        "security/currency_account_security.xml",
        "views/account_move_views.xml",
        "views/res_currency_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "currency_account/static/src/**/*",
        ],
    },
    "post_init_hook": "post_init_hook",
    "installable": True,
    "auto_install": False,
}
