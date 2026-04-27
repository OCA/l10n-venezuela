{
    "name": "res_currency_rate_provider_bcv",
    "summary": """
        Automate currency exchange rates from Central Bank of Venezuela (BCV).
    """,
    "version": "19.0.1.0.0",
    "development_status": "Beta",
    "category": "Financial Management/Configuration",
    "website": "https://github.com/OCA/l10n-venezuela",
    "author": "Luis Pinzón, Odoo Community Association (OCA)",
    "maintainers": ["lapinzon", "erwinscc88"],
    "license": "AGPL-3",
    "application": False,
    "installable": True,
    "depends": ["currency_rate_update"],
    "data": [
        "views/res_currency_rate_update_wizard_view.xml",
    ],
}
