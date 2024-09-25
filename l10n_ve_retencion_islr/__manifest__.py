# -*- coding: utf-8 -*-
{
    "name": "Gestión de Retenciones de impuestos sobre la renta según las leyes venezolanas",
    "version": "1.1",
    "author": "Empero",
    "license": "AGPL-3",
    "website": "http://empero.com.ve",
    "category": 'Generic Modules/Accounting',
    "depends": [
                "l10n_ve_retencion_iva"
    ],
    'data': [
        'data/ir_sequence_data.xml',
        'views/wh_islr_view.xml',
        'reports/ret_islr_report.xml'
    ],
    'installable': True,
}
 
