# Copyright 2026 BWEALTHICS LLC
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "Venezuela - Municipal Tax",
    "summary": "Estimate municipal tax and create its monthly provision entry",
    "version": "19.0.1.0.0",
    "category": "Accounting/Localizations",
    "website": "https://github.com/OCA/l10n-venezuela",
    "author": "BWEALTHICS LLC, Odoo Community Association (OCA)",
    "maintainers": ["bwealthics"],
    "license": "AGPL-3",
    "development_status": "Beta",
    "depends": ["l10n_ve"],
    "data": [
        "security/ir.model.access.csv",
        "views/res_config_settings_views.xml",
        "wizards/municipal_tax_wizard_views.xml",
    ],
    "installable": True,
}
