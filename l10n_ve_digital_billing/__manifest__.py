# Copyright 2026 BWEALTHICS LLC
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "Venezuela - Digital Billing",
    "summary": "Connect Venezuelan customer documents to an authorized "
    "digital printing house",
    "version": "19.0.1.0.0",
    "category": "Accounting/Localizations",
    "website": "https://github.com/OCA/l10n-venezuela",
    "author": "BWEALTHICS LLC, Odoo Community Association (OCA)",
    "maintainers": ["bwealthics"],
    "license": "AGPL-3",
    "development_status": "Beta",
    "depends": ["l10n_ve_fiscal_document"],
    "external_dependencies": {"python": ["requests"]},
    "data": [
        "security/ir.model.access.csv",
        "data/ir_cron.xml",
        "views/account_move_views.xml",
        "views/edoc_log_views.xml",
        "views/res_config_settings_views.xml",
        "wizard/l10n_ve_edoc_cancel_wizard_views.xml",
    ],
    "installable": True,
}
