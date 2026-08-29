# Copyright 2026 BWEALTHICS LLC
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "Venezuela - IGTF",
    "summary": "Record IGTF on payments in foreign currency or cryptoassets",
    "version": "19.0.1.0.0",
    "category": "Accounting/Localizations",
    "website": "https://github.com/OCA/l10n-venezuela",
    "author": "BWEALTHICS LLC, Odoo Community Association (OCA)",
    "maintainers": ["bwealthics"],
    "license": "AGPL-3",
    "development_status": "Beta",
    "depends": ["l10n_ve"],
    "data": [
        "views/account_journal_views.xml",
        "views/account_payment_views.xml",
        "views/res_config_settings_views.xml",
        "wizards/account_payment_register_views.xml",
    ],
    "installable": True,
}
