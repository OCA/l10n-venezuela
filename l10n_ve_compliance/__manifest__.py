# Copyright 2026 BWEALTHICS LLC
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "Venezuela - Fiscal Compliance",
    "summary": "Fiscal localization umbrella with subscribed audit logging",
    "version": "19.0.1.0.0",
    "category": "Accounting/Localizations",
    "website": "https://github.com/OCA/l10n-venezuela",
    "author": "BWEALTHICS LLC, Odoo Community Association (OCA)",
    "maintainers": ["bwealthics"],
    "license": "AGPL-3",
    "development_status": "Beta",
    "countries": ["ve"],
    "depends": [
        "auditlog",
        "l10n_ve",
        "l10n_ve_fiscal_books",
        "l10n_ve_invoice_format",
        "l10n_ve_igtf",
        "l10n_ve_municipal_tax",
        "l10n_ve_wh_iva",
        "l10n_ve_wh_islr",
    ],
    "post_init_hook": "post_init_hook",
    "installable": True,
}
