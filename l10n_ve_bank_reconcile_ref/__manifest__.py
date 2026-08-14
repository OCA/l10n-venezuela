# Copyright 2026 andyengit
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "Venezuela Bank Reconcile by Reference",
    "summary": "Auto-match bank statements by payment/invoice reference suffixes",
    "version": "18.0.1.0.0",
    "category": "Accounting",
    "website": "https://github.com/OCA/l10n-venezuela",
    "author": "andyengit, Odoo Community Association (OCA)",
    "maintainers": ["andyengit"],
    "license": "AGPL-3",
    "depends": [
        "account_reconcile_oca",
        "account_reconcile_model_oca",
    ],
    "data": [
        "data/account_reconcile_model_data.xml",
        "views/account_reconcile_model_views.xml",
    ],
    "installable": True,
}
