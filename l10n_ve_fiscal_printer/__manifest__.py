# Copyright 2026 BWEALTHICS LLC
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

{
    "name": "Venezuela - Fiscal Printer",
    "summary": "Print Venezuelan fiscal documents through a local bridge",
    "version": "19.0.1.0.0",
    "category": "Accounting/Localizations/Point of Sale",
    "website": "https://github.com/OCA/l10n-venezuela",
    "author": "BWEALTHICS LLC, Odoo Community Association (OCA)",
    "maintainers": ["bwealthics"],
    "license": "LGPL-3",
    "development_status": "Beta",
    "countries": ["ve"],
    "depends": ["l10n_ve_fiscal_document", "point_of_sale"],
    "data": [
        "views/res_config_settings_views.xml",
        "views/pos_order_views.xml",
        "views/pos_payment_method_views.xml",
        "views/account_move_views.xml",
    ],
    "assets": {
        "point_of_sale._assets_pos": [
            "l10n_ve_fiscal_printer/static/src/app/**/*",
        ],
        "web.assets_backend": [
            "l10n_ve_fiscal_printer/static/src/app/utils/fiscal_bridge.esm.js",
            "l10n_ve_fiscal_printer/static/src/backend/**/*",
        ],
        "web.assets_unit_tests": [
            "l10n_ve_fiscal_printer/static/src/app/utils/fiscal_bridge.esm.js",
            "l10n_ve_fiscal_printer/static/tests/**/*",
        ],
    },
    "installable": True,
}
