import setuptools

with open('VERSION.txt', 'r') as f:
    version = f.read().strip()

setuptools.setup(
    name="odoo15-addons-oca-l10n-venezuela",
    description="Meta package for oca-l10n-venezuela Odoo addons",
    version=version,
    install_requires=[
        'odoo15-addon-l10n_ve_base',
        'odoo15-addon-l10n_ve_invoice_reports',
        'odoo15-addon-l10n_ve_vat_ledger',
        'odoo15-addon-l10n_ve_withholding',
        'odoo15-addon-territorial_pd',
        'odoo15-addon-unique_vat_by_partner',
        'odoo15-addon-vat_type_partner',
    ],
    classifiers=[
        'Programming Language :: Python',
        'Framework :: Odoo',
        'Framework :: Odoo :: 15.0',
    ]
)
