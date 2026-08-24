# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    "name": "Venezuela - Loyalty POS",
    "summary": "Aplica programas loyalty del POS como descuentos globales SENIAT",
    "website": "https://github.com/OCA/l10n-venezuela",
    "icon": "/poweredbyandy_saas/static/description/icon.png",
    "countries": ["ve"],
    "version": "18.0.1.3.9",
    "author": "andyengit, Odoo Community Association (OCA)",
    "maintainers": ["andyengit"],
    "category": "Sales/Point of Sale",
    "depends": [
        "l10n_ve_loyalty",
        "pos_loyalty",
        "l10n_ve_pos",
        "l10n_ve_fiscal_serial",
    ],
    "data": [
        "data/loyalty_ewallet_product_data.xml",
    ],
    "assets": {
        "point_of_sale._assets_pos": [
            "l10n_ve_loyalty_pos/static/src/**/*.esm.js",
            "l10n_ve_loyalty_pos/static/src/**/*.xml",
        ],
    },
    "license": "AGPL-3",
    "installable": True,
    "auto_install": True,
}
