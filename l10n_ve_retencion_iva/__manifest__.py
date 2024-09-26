# -*- coding: utf-8 -*-
{
    "name": "Gestión de retenciones sobre IVA según las leyes venezolanas",
    "version": "1.1",
    "author": "Empero",
    "license": "AGPL-3",
    "website": "http://empero.com.ve",
    "category": 'Generic Modules/Accounting',
    "depends": ['account', 'l10n_ve_account',
    'l10n_ve_fiscal_requirements'
    ],
    'data': [
        'data/ir_sequence_data.xml',
        'views/account_view.xml',
        'views/wh_iva_view.xml',
        'views/account_invoice_view.xml',
        'reports/ret_iva_report.xml',
    ],
    'installable': True,
}
