{
    "name": "Venezuela - IGTF en Punto de Venta",
    "summary": (
        "Calcula el IGTF en el POS según monedas configuradas "
        "en l10n_ve_igtf y la moneda del método de pago."
    ),
    "version": "18.0.1.1.5",
    "category": "Point of Sale/Localizations",
    "author": "andyengit, Odoo Community Association (OCA)",
    "maintainer": "andyengit",
    "website": "https://github.com/OCA/l10n-venezuela",
    "license": "AGPL-3",
    "depends": [
        "l10n_ve_pos",
        "l10n_ve_igtf",
        "currency_pos",
    ],
    "data": [
        "views/pos_payment_views.xml",
        "views/pos_order_views.xml",
    ],
    "assets": {
        "point_of_sale._assets_pos": [
            "l10n_ve_pos_igtf/static/src/overrides/models/pos_payment.esm.js",
            "l10n_ve_pos_igtf/static/src/overrides/models/pos_order.esm.js",
            "l10n_ve_pos_igtf/static/src/overrides/screens/payment_screen.esm.js",
            "l10n_ve_pos_igtf/static/src/overrides/screens/payment_screen.xml",
            "l10n_ve_pos_igtf/static/src/overrides/screens/payment_lines/payment_lines.esm.js",
            "l10n_ve_pos_igtf/static/src/overrides/screens/payment_lines/payment_lines.xml",
        ],
    },
    "installable": True,
    "application": False,
}
