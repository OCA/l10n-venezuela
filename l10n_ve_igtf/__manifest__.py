{
    "name": "Venezuela IGTF",
    "version": "18.0.1.0.0",
    "website": "https://github.com/OCA/l10n-venezuela",
    "icon": "/poweredbyandy_saas/static/description/icon.png",
    "countries": ["ve"],
    "author": "Odoo Community Association (OCA)",
    "category": "Accounting/Localizations",
    "depends": ["web", "account", "l10n_ve_seniat", "currency_account"],
    "data": [
        "security/ir.model.access.csv",
        "views/account_move_views.xml",
        "views/account_payment_views.xml",
        "views/account_payment_register_views.xml",
        "views/res_config_settings.xml",
        "wizard/unreconcile_igtf_payment_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "l10n_ve_igtf/static/src/components/account_payment_field/account_payment.xml",
            "l10n_ve_igtf/static/src/components/account_payment_field/account_payment_field_patch.js",
            "l10n_ve_igtf/static/src/components/tax_totals/tax_totals_igtf.xml",
            "l10n_ve_igtf/static/src/components/tax_totals/tax_totals_company_currency_igtf.xml",
        ],
    },
    "license": "AGPL-3",
    "post_init_hook": "post_init_hook",
}
