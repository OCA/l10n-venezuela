{
    "name": "Venezuela - Point of Sale",
    "summary": "Localización venezolana para el Punto de Venta.",
    "website": "https://github.com/OCA/l10n-venezuela",
    "icon": "/poweredbyandy_saas/static/description/icon.png",
    "countries": ["ve"],
    "version": "18.0.1.3.7",
    "author": "andyengit, Odoo Community Association (OCA)",
    "maintainer": "andyengit",
    "category": "Point of Sale/Localizations",
    "depends": [
        "point_of_sale",
        "l10n_ve_seniat",
        "l10n_ve_stock",
        "l10n_ve_exchange_rates",
    ],
    "data": [
        "views/product_view.xml",
        "views/pos_order_views.xml",
    ],
    "assets": {
        "point_of_sale._assets_pos": [
            "l10n_ve_pos/static/src/**/*.esm.js",
            "l10n_ve_pos/static/src/**/*.xml",
            "l10n_ve_pos/static/src/**/*.scss",
        ],
    },
    "license": "AGPL-3",
    "installable": True,
    "application": False,
}
