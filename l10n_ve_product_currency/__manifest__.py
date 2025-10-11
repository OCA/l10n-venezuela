# This module is adapted from ADHOC module: https://github.com/ingadhoc/product/tree/18.0/product_currency
{
    "name": "Product Currency",
    "version": "18.0.1.0.0",
    "category": "Products",
    "sequence": 10,
    "summary": "",
    "author": ["andyengit", "ADHOC SA"],
    "images": [],
    "depends": [
        "product",
    ],
    "data": [
        "views/product_template_views.xml",
        "security/product_currency_security.xml",
    ],
    "demo": [
        "demo/product_product_demo.xml",
    ],
    "installable": True,
    "auto_install": False,
    "application": False,
}
