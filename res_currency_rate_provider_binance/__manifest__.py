{
    "name": "Currency rate provider: BNB P2P",
    "summary": """Currency rate provider for Binance""",
    "version": "18.0.1.1.2",
    "category": "Financial Management/Configuration",
    "author": "Anderson Armeya, Odoo Community Association (OCA)",
    "maintainers": ["andyengit"],
    "license": "AGPL-3",
    "application": False,
    "installable": True,
    "depends": ["currency_rate_update"],
    "data": [
        "data/res_currency_data.xml",
        "views/res_currency_rate_provider.xml",
    ],
}
