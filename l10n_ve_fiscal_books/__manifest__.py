# Copyright 2026 BWEALTHICS LLC
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

{
    "name": "Venezuela - Fiscal Books",
    "summary": "Generate Venezuelan VAT purchase and sales books in XLSX",
    "version": "19.0.1.0.0",
    "category": "Accounting/Localizations",
    "countries": ["ve"],
    "website": "https://github.com/OCA/l10n-venezuela",
    "author": "BWEALTHICS LLC, Odoo Community Association (OCA)",
    "maintainers": ["bwealthics"],
    "license": "LGPL-3",
    "development_status": "Beta",
    "depends": ["l10n_ve_fiscal_document", "point_of_sale"],
    "external_dependencies": {"python": ["xlsxwriter"]},
    "data": [
        "security/ir.model.access.csv",
        "views/account_move_views.xml",
        "views/paper_batch_views.xml",
        "views/res_config_settings_views.xml",
        "wizards/fiscal_book_wizard_views.xml",
    ],
    "post_init_hook": "post_init_hook",
    "installable": True,
}
