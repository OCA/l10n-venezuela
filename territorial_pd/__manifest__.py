################################################################################
# Author: SINAPSYS GLOBAL SA || MASTERCORE SAS
# Copyleft: 2020-Present.
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).
#
#
################################################################################
{
    "name": "Municipalities and Parishes",
    "summary": """
        Political Division Module.
        This is a Module that contains Municipaly and
        Parish Models for deeper political division of Country and State""",
    "author": "Sinapsys Global SA, MASTERCORE SAS, Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/l10n-venezuela",
    "category": "Localization",
    "license": "LGPL-3",
    "version": "0.1",
    "depends": ["base", "contacts"],
    "data": [
        "data/res.country.csv",
        "data/res.country.state.csv",
        "data/res.country.state.municipality.csv",
        "data/res.country.state.municipality.parish.csv",
        "security/ir.model.access.csv",
        "views/res_country_state_municipality.xml",
        "views/res_country_state_municipality_parish.xml",
    ],
}
