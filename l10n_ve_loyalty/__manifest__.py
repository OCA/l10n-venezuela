# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    "name": "Venezuela - Loyalty & Discounts",
    "summary": "Descuentos globales SENIAT y adaptacion de Coupons & Loyalty para Venezuela",
    "website": "https://github.com/OCA/l10n-venezuela",
    "icon": "/poweredbyandy_saas/static/description/icon.png",
    "countries": ["ve"],
    "version": "18.0.1.0.15",
    "author": "andyengit, Odoo Community Association (OCA)",
    "maintainers": ["andyengit"],
    "category": "Accounting/Localizations",
    "depends": [
        "account",
        "loyalty",
        "web",
        "currency_account",
        "l10n_ve_seniat",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/l10n_ve_discount_reason_data.xml",
        "report/account_tax_totals_templates.xml",
        "wizard/l10n_ve_account_move_discount_wizard_views.xml",
        "wizard/l10n_ve_account_move_post_discount_wizard_views.xml",
        "views/account_move_views.xml",
        "views/l10n_ve_discount_reason_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "l10n_ve_loyalty/static/src/components/tax_totals/tax_totals.js",
            "l10n_ve_loyalty/static/src/components/tax_totals/tax_totals_global_discount.xml",
            "l10n_ve_loyalty/static/src/components/tax_totals/tax_totals.scss",
        ],
    },
    "license": "AGPL-3",
    "installable": True,
}
