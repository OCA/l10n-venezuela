# Copyright 2026 BWEALTHICS LLC
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

{
    "name": "Venezuela - Invoice Format",
    "summary": "Add Venezuelan legal information to invoice reports",
    "version": "19.0.1.0.0",
    "category": "Accounting/Localizations",
    "website": "https://github.com/OCA/l10n-venezuela",
    "author": "BWEALTHICS LLC, Odoo Community Association (OCA)",
    "maintainers": ["bwealthics"],
    "license": "LGPL-3",
    "development_status": "Beta",
    "depends": ["l10n_ve_fiscal_document"],
    "data": [
        "data/res_country_data.xml",
        "views/res_config_settings_views.xml",
        "report/report_invoice.xml",
    ],
    "installable": True,
}
