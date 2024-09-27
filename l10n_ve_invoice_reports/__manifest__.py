################################################################################
# Author      : SINAPSYS GLOBAL SA || MASTERCORE SAS
# Copyright(c): 2021-Present.
# License URL : AGPL-3
################################################################################

{
    "name": "Comprobantes para Factura Venezolana",
    "version": "14.0.0.1.0",
    "author": "SINAPSYS GLOBAL SA, MASTERCORE SAS, Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/l10n-venezuela",
    "license": "AGPL-3",
    "category": "Localization / Venezuela",
    "depends": [
        "base",
        "account",
        "l10n_ve_base",
        "l10n_ve_withholding",
    ],
    "data": [
        "template/report_invoice_ve.xml",
        "data/external_layout_report.xml",
    ],
    "auto_install": False,
    "application": False,
    "installable": True,
}
