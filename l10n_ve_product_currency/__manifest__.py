# This module is adapted from ADHOC module: https://github.com/ingadhoc/product/tree/18.0/product_currency
{
    "name": "Product Currency",
    "version": "18.0.1.0.0",
    "category": "Products",
    "sequence": 10,
    "summary": "Select currencies on product templates",
    "author": "Andyengit,Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/l10n-venezuela",
    "license": "LGPL-3",
    "images": [],
    "depends": [
        "product",
    ],
    "data": [
        "views/res_config_settings_views.xml",
        "views/product_template_views.xml",
        "security/product_currency_security.xml",
    ],
    "demo": [],
    "installable": True,
    "auto_install": False,
    "application": False,
}
