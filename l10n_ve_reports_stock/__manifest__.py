# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    "name": "Venezuelan Reports - Stock Inventory Book",
    "icon": "/poweredbyandy_saas/static/description/icon.png",
    "summary": "Libro de Inventario para reportes SENIAT",
    "category": "Inventory/Inventory",
    "author": "andyengit, Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/l10n-venezuela",
    "version": "18.0.1.0.0",
    "maintainers": ["andyengit"],
    "depends": [
        "l10n_ve_reports",
        "stock",
        "l10n_ve_seniat",
    ],
    "data": [
        "data/inventory_book_report.xml",
        "data/inventory_book_report_actions.xml",
        "views/stock_warehouse_views.xml",
        "views/seniat_menuitems.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "l10n_ve_reports_stock/static/src/components/inventory_book_report/*.js",
            "l10n_ve_reports_stock/static/src/components/inventory_book_report/*.xml",
        ],
    },
    "installable": True,
    "license": "AGPL-3",
}
