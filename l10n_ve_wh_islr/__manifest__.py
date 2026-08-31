# Copyright 2026 BWEALTHICS LLC
# Part of l10n_ve_wh_islr. License LGPL-3.

{
    "name": "Venezuela - ISLR Withholding",
    "summary": "Manage Venezuelan income tax withholdings and SENIAT XML exports",
    "version": "19.0.1.0.0",
    "category": "Accounting/Localizations",
    "website": "https://github.com/OCA/l10n-venezuela",
    "author": "BWEALTHICS LLC, Odoo Community Association (OCA)",
    "maintainers": ["bwealthics"],
    "license": "LGPL-3",
    "development_status": "Beta",
    "countries": ["ve"],
    "depends": ["l10n_ve"],
    "data": [
        "security/islr_security.xml",
        "security/ir.model.access.csv",
        "data/ir_sequence.xml",
        "data/ut_data.xml",
        "data/islr_concepts.xml",
        "views/ut_views.xml",
        "views/islr_concept_views.xml",
        "views/islr_voucher_views.xml",
        "views/res_partner_views.xml",
        "views/res_config_settings_views.xml",
        "views/account_payment_register_views.xml",
        "wizards/islr_xml_export_views.xml",
        "reports/arc_islr_report.xml",
    ],
    "installable": True,
}
