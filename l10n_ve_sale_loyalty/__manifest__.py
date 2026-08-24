# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    "name": "Venezuela SENIAT - Sale Loyalty",
    "summary": "Descuentos globales SENIAT en pedidos de venta",
    "website": "https://github.com/OCA/l10n-venezuela",
    "countries": ["ve"],
    "author": "andyengit, Odoo Community Association (OCA)",
    "maintainers": ["andyengit"],
    "category": "Sales/Localizations",
    "version": "18.0.1.0.0",
    "depends": [
        "l10n_ve_seniat_sale",
        "l10n_ve_loyalty",
    ],
    "data": [
        "security/ir.model.access.csv",
        "wizard/sale_order_discount_views.xml",
    ],
    "license": "AGPL-3",
    "installable": True,
    "auto_install": ["l10n_ve_seniat_sale", "l10n_ve_loyalty"],
}
