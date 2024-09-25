# coding: utf-8
###########################################################################
#    Module Writen to OpenERP, Open Source Management Solution
#    Copyright (C) OpenERP Venezuela (<http://openerp.com.ve>).
#    All Rights Reserved
###############################################################################
#    Credits:
#    Coded by: Vauxoo C.A.
#    Planified by: Nhomar Hernandez
#    Audited by: Vauxoo C.A.
#############################################################################
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as published
#    by the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
###############################################################################
{
    "name": "Venezuelan Fiscal Requirements",
    "version": "1.0",
    "author": "Vauxoo",
    "license": "AGPL-3",
    "website": "http://vauxoo.com",
    "category": 'Localization',
    "depends": [
        "account",
        "base_vat",
        "account_accountant",
        "account_voucher",
        "account_cancel",
        "debit_credit_note"
    ],
    'data': [
        'data/l10n_ut_data.xml',
        'data/seniat_url_data.xml',
        'data/ir_sequence.xml',
        'security/security_view.xml',
        'security/ir.model.access.csv',
        'view/fr_view.xml',
        'wizard/wizard_invoice_nro_ctrl_view.xml',
        'wizard/wizard_url_seniat_view.xml',
        'wizard/update_info_partner.xml',
        'wizard/account_invoice_debit_view.xml',
        'wizard/search_info_partner_seniat.xml',
        'wizard/wizard_nro_ctrl_view.xml',
        'view/res_company_view.xml',
        'view/l10n_ut_view.xml',
        'wizard/wizard_update_name_view.xml',
        'view/partner_view.xml',
        'view/account_inv_refund_nctrl_view.xml',
        'view/account_tax_view.xml',
        'view/account_invoice_view.xml',
    ],
    'demo': [
        'demo/demo_partners.xml',
        'demo/demo_journal.xml',
        'demo/demo_invoice.xml',
        'demo/demo_taxes.xml',
    ],
    'test': [
        'test/account_customer_invoice.yml',
        'test/account_supplier_invoice.yml',
        'test/fr_vat_search_test.yml',
        'test/fr_ut_test.yml',
        'test/fr_vat_test.yml',
        'test/fr_tax_test.yml',
        'test/fr_address.yml',
        'test/fr_sale_test.yml',
        'test/fr_purchase_test.yml',
        'test/fr_control_number.yml',
        'test/fr_damaged.yml',
        #        'test/fr_debit_note.yml',
        #        'test/fr_refund_note.yml',
    ],
    'installable': True,
}
