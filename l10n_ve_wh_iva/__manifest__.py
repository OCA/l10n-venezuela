# Copyright 2026 BWEALTHICS LLC
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

{
    "name": "Venezuela - VAT Withholding",
    "summary": "Manage Venezuelan VAT withholding in customer and vendor payments",
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
        "security/ir.model.access.csv",
        "data/ir_sequence_data.xml",
        "views/iva_wh_voucher_views.xml",
        "views/account_payment_register_views.xml",
        "views/res_partner_views.xml",
        "views/res_config_settings_views.xml",
        "wizards/iva_txt_export_views.xml",
        "report/iva_wh_voucher_report.xml",
    ],
    "installable": True,
}
