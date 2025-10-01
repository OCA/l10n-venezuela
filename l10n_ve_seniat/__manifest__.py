# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    "name": "Venezuela SENIAT - Accounting",
    "website": "https://www.odoo.com/documentation/18.0/applications/finance/fiscal_localizations.html",
    "icon": "/account/static/description/l10n.png",
    "countries": ["ve"],
    "author": "Anderson Armeya, Odoo Community Association (OCA)",
    "category": "Accounting/Localizations/Account Charts",
    "depends": ["base", "account"],
    "excludes": ["web_studio"],
    "demo": [
        "demo/demo_company.xml",
    ],
    "data": [
        "security/ir.model.access.csv",
        "security/res_groups.xml",
        "data/res_country.xml",
        "data/res.country.state.csv",
        "data/res.country.municipality.csv",
        "data/res.country.parish.csv",
        "views/account_move_views.xml",
        "views/res_country_municipality_views.xml",
        "views/res_country_parish_views.xml",
        "views/res_partner_views.xml",
        "views/report_layout.xml",
        "views/menuitems.xml",
    ],
    "license": "AGPL-3",
}
