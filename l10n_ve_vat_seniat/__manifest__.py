# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    "name": "Venezuela - SENIAT RIF Lookup",
    "summary": "Query SENIAT BuscaRif taxpayer data from contacts.",
    "version": "18.0.1.0.0",
    "category": "Localization",
    "author": "andyengit, Odoo Community Association (OCA)",
    "maintainers": ["andyengit"],
    "website": "https://github.com/OCA/l10n-venezuela",
    "license": "AGPL-3",
    "countries": ["ve"],
    "depends": ["contacts", "l10n_ve_seniat", "l10n_ve_withholding"],
    "data": [
        "views/res_partner_views.xml",
    ],
    "external_dependencies": {
        "python": ["requests", "Pillow", "pytesseract"],
    },
    "installable": True,
    "application": False,
}
