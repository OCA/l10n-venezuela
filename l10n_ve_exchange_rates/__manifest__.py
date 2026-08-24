{
    "name": "Venezuela  - Tasas de Cambio en Tooltip",
    "version": "18.0.1.0.1",
    "category": "Extra Tools",
    "author": "Andyengit,Odoo Community Association (OCA)",
    "summary": "Muestra las tasas de cambio configuradas en un tooltip de la navbar principal.",  # noqa: E501
    "website": "https://github.com/OCA/l10n-venezuela",
    "depends": ["web", "base"],
    "data": [
        "views/res_currency_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "l10n_ve_exchange_rates/static/src/**/*",
        ],
    },
    "license": "LGPL-3",
    "installable": True,
    "auto_install": False,
}
