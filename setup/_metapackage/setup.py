import setuptools

with open('VERSION.txt', 'r') as f:
    version = f.read().strip()

setuptools.setup(
    name="odoo-addons-oca-l10n-venezuela",
    description="Meta package for oca-l10n-venezuela Odoo addons",
    version=version,
    install_requires=[
        'odoo-addon-res_currency_rate_provider_BCV>=16.0dev,<16.1dev',
    ],
    classifiers=[
        'Programming Language :: Python',
        'Framework :: Odoo',
        'Framework :: Odoo :: 16.0',
    ]
)
