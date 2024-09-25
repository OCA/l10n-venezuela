# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name' : 'Venezuela - Accounting',
    'author': 'Empero C.A',
    'category': 'Localization',
    'depends': ['account',
                'account_accountant',
                'base_vat',
    ],
    'data': [
             'data/l10n_ve_chart_data.xml',
             'data/account_tax_data.xml',
             'data/account_chart_template_data.yml',
             'views/account_account_type_view.xml'
    ],
}
