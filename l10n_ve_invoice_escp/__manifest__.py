{
    "name": "Venezuela — Factura ESC/P Epson (WebUSB)",
    "version": "18.0.1.0.13",
    "category": "Accounting/Localizations",
    "summary": "Impresión de facturas VE en papel continuo vía WebUSB (ESC/P Epson)",
    "author": "andyengit, Odoo Community Association (OCA)",
    "maintainer": "andyengit",
    "website": "https://github.com/OCA/l10n-venezuela",
    "license": "AGPL-3",
    "depends": ["l10n_ve_seniat"],
    "assets": {
        "web.assets_backend": [
            "l10n_ve_invoice_escp/static/src/js/l10n_ve_invoice_escp_print_action.esm.js",
        ],
    },
    "installable": True,
}
