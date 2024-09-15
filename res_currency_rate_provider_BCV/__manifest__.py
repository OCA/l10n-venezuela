{
    "name": "res_currency_rate_provider_BCV",
    "summary": """OCA version for BCV scrapping rates
       """,
    "version": "16.0.1.1.2",
    "development_status": "Beta",
    "category": "Financial Management/Configuration",
    "website": "https://github.com/OCA/l10n-venezuela",
    "author": "Luis Pinzón, Odoo Community Association (OCA)",
    "maintainers": ["lapinzon"],
    "license": "AGPL-3",
    "application": False,
    "installable": True,
    "depends": ["currency_rate_update"],
    "data": [
        "views/res_currency_rate_update_wizard.xml",
        "views/res_currency_rate_provider.xml",
    ],
}
