# -*- coding: utf-8 -*-
{
    "name": "Requerimientos Fiscales Venezolanos",
    "version": "1.0",
    "author": "Konos",
    "license": "AGPL-3",
    "website": "http://konos.cl",
    "category": 'Localization',
    "description":
        """
Requerimientos Fiscales Venezolanos
===================================

Basado en EmperoVE.
     """,
    "maintainer": "Konos",
    "depends": [
        "account",
        "l10n_ve"
    ],
    'data': [
        
        'views/partner_view.xml',
        'views/company_view.xml',
        'views/account_invoice_view.xml',
        'reports/fiscal_invoice.xml'
    ],
    'installable': True,
}
