# -*- coding: utf-8 -*-
{
    "name": "Requerimientos Fiscales Venezolanos",
    "version": "1.0",
    "author": "Empero",
    "license": "AGPL-3",
    "website": "http://empero.com.ve",
    "category": 'Localization',
    "depends": [
        "account",
        "account_accountant",
        "l10n_ve_account"
    ],
    'data': [
        
        'views/partner_view.xml',
        'views/company_view.xml',
        'reports/fiscal_invoice.xml'
    ],
    'installable': True,
}
