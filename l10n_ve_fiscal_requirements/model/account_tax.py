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

from openerp.osv import fields, osv


class AccountTax(osv.osv):
    _inherit = 'account.tax'
    _columns = {
        'appl_type': fields.selection(
            [('exento', 'Exempt'),
             ('sdcf', 'Not entitled to tax credit'),
             ('general', 'General Aliquot'),
             ('reducido', 'Reducted Aliquot'),
             ('adicional', 'General Aliquot + Additional')],
            'Aliquot Type',
            required=False,
            help='Specify the aliquote type for the tax so it can be processed'
                 ' accrordly when the sale/purchase book is generatred'),
    }
