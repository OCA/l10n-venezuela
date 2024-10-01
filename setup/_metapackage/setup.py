import setuptools

with open('VERSION.txt', 'r') as f:
    version = f.read().strip()

setuptools.setup(
    name="odoo13-addons-oca-l10n-venezuela",
    description="Meta package for oca-l10n-venezuela Odoo addons",
    version=version,
    install_requires=[
        'odoo13-addon-l10n_ve_account_financial_amount',
        'odoo13-addon-l10n_ve_account_payment_fix',
        'odoo13-addon-l10n_ve_account_payment_group',
        'odoo13-addon-l10n_ve_account_payment_group_document',
        'odoo13-addon-l10n_ve_account_withholding',
        'odoo13-addon-l10n_ve_account_withholding_automatic',
        'odoo13-addon-l10n_ve_base',
        'odoo13-addon-l10n_ve_vat_ledger',
        'odoo13-addon-l10n_ve_withholding',
        'odoo13-addon-territorial_pd',
    ],
    classifiers=[
        'Programming Language :: Python',
        'Framework :: Odoo',
        'Framework :: Odoo :: 13.0',
    ]
)
