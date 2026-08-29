# Copyright 2026 BWEALTHICS LLC
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "Venezuela - POS Payments in Bolivars",
    "summary": "Record exact VES amounts for foreign-currency POS payments",
    "version": "19.0.1.0.0",
    "category": "Point of Sale",
    "website": "https://github.com/OCA/l10n-venezuela",
    "author": "BWEALTHICS LLC, Odoo Community Association (OCA)",
    "maintainers": ["bwealthics"],
    "license": "AGPL-3",
    "development_status": "Beta",
    "depends": ["point_of_sale"],
    "data": [
        "views/pos_payment_method_views.xml",
        "views/pos_payment_views.xml",
    ],
    "assets": {
        "point_of_sale._assets_pos": [
            "l10n_ve_pos_bs/static/src/app/utils/order_payment_validation.esm.js",
        ],
    },
    "installable": True,
}
