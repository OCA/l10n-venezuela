# Copyright 2026 BWEALTHICS LLC
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

{
    "name": "Venezuela - Fiscal Document",
    "summary": "Store Venezuelan fiscal document identification data",
    "version": "19.0.1.0.0",
    "category": "Accounting/Localizations",
    "website": "https://github.com/OCA/l10n-venezuela",
    "author": "BWEALTHICS LLC, Odoo Community Association (OCA)",
    "maintainers": ["bwealthics"],
    "license": "LGPL-3",
    "development_status": "Beta",
    "depends": ["l10n_ve"],
    "data": [
        "views/account_journal_views.xml",
        "views/account_move_views.xml",
    ],
    "post_init_hook": "post_init_hook",
    "installable": True,
}
