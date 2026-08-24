# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    "name": "Venezuela EDI Facturacion Digital",
    "summary": (
        "Base para facturacion digital Venezuela " "(validaciones, payload y flujo)"
    ),
    "version": "18.0.1.12.0",
    "category": "Accounting/Localizations",
    "author": "andyengit, Odoo Community Association (OCA)",
    "maintainers": ["andyengit"],
    "website": "https://github.com/OCA/l10n-venezuela",
    "license": "AGPL-3",
    "countries": ["ve"],
    "depends": [
        "l10n_ve_seniat",
        "l10n_ve_withholding",
        "l10n_ve_igtf",
        "l10n_ve_stock",
    ],
    "data": [
        "views/res_config_settings_views.xml",
        "views/account_journal_views.xml",
        "views/account_move_views.xml",
        "views/account_retention_views.xml",
        "views/stock_picking_views.xml",
        "views/portal_templates.xml",
    ],
    "assets": {
        "web.assets_backend": [
            (
                "l10n_ve_edi/static/src/components/edi_unsent_dashboard/"
                "edi_unsent_dashboard.esm.js"
            ),
            (
                "l10n_ve_edi/static/src/components/edi_unsent_dashboard/"
                "edi_unsent_dashboard.xml"
            ),
            (
                "l10n_ve_edi/static/src/components/"
                "edi_seniat_invoice_dashboard/"
                "edi_seniat_invoice_dashboard.esm.js"
            ),
            (
                "l10n_ve_edi/static/src/views/account_dashboard_kanban/"
                "edi_account_dashboard_kanban.esm.js"
            ),
            (
                "l10n_ve_edi/static/src/views/account_dashboard_kanban/"
                "edi_account_dashboard_kanban.xml"
            ),
            "l10n_ve_edi/static/src/scss/edi_unsent_dashboard.scss",
        ],
    },
    "installable": True,
    "application": False,
}
