import setuptools

with open('VERSION.txt', 'r') as f:
    version = f.read().strip()

setuptools.setup(
    name="odoo14-addons-oca-l10n-venezuela",
    description="Meta package for oca-l10n-venezuela Odoo addons",
    version=version,
    install_requires=[
        'odoo14-addon-l10n_ve_account_financial_amount',
        'odoo14-addon-l10n_ve_account_payment_fix',
        'odoo14-addon-l10n_ve_account_payment_group',
        'odoo14-addon-l10n_ve_account_payment_group_document',
        'odoo14-addon-l10n_ve_account_withholding',
        'odoo14-addon-l10n_ve_account_withholding_automatic',
        'odoo14-addon-l10n_ve_base',
        'odoo14-addon-l10n_ve_invoice_reports',
        'odoo14-addon-l10n_ve_vat_ledger',
        'odoo14-addon-l10n_ve_withholding',
        'odoo14-addon-territorial_pd',
    ],
    classifiers=[
        'Programming Language :: Python',
        'Framework :: Odoo',
        'Framework :: Odoo :: 14.0',
    ]
)
