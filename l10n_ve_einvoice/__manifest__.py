# Copyright 2026 BWEALTHICS LLC
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

{
    "name": "Venezuela - Electronic Invoicing",
    "summary": "Provider-neutral electronic invoicing for Venezuela",
    "version": "19.0.1.0.0",
    "category": "Accounting/Localizations",
    "website": "https://github.com/OCA/l10n-venezuela",
    "author": "BWEALTHICS LLC, Odoo Community Association (OCA)",
    "maintainers": ["bwealthics"],
    "license": "LGPL-3",
    "development_status": "Beta",
    "countries": ["ve"],
    "depends": ["l10n_ve_fiscal_document"],
    "data": [
        "security/ir.model.access.csv",
        "security/l10n_ve_edoc_security.xml",
        "data/ir_cron.xml",
        "views/account_move_views.xml",
        "views/edoc_log_views.xml",
        "views/res_config_settings_views.xml",
        "wizard/l10n_ve_edoc_cancel_wizard_views.xml",
    ],
    "installable": True,
}
