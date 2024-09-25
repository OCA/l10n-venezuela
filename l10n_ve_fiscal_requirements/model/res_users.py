#!/usr/bin/python
# -*- encoding: utf-8 -*-
###########################################################################
#    Module Writen to OpenERP, Open Source Management Solution
#    Copyright (C) OpenERP Venezuela (<http://openerp.com.ve>).
#    All Rights Reserved
###############################################################################
#    Credits:
#    Coded by: Humberto Arocha           <humberto@vauxoo.com>
#              María Gabriela Quilarque  <gabriela@vauxoo.com>
#              Nhomar Hernandez          <nhomar@vauxoo.com>
#    Planified by: Humberto Arocha
#    Finance by: Helados Gilda, C.A. http://heladosgilda.com.ve
#    Audited by: Humberto Arocha humberto@openerp.com.ve
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
##############################################################################

from openerp.osv import osv


class res_users(osv.osv):
    _inherit = 'res.users'

    def create(self, cr, uid, vals, context=None):
        """ To create a new record,
        adds a Boolean field to true
        indicates that the partner is a company
        """
        if context is None:
            context = {}
        context.update({'create_company': True})
        return super(res_users, self).create(cr, uid, vals, context=context)

    def write(self, cr, uid, ids, values, context=None):
        """ To write a new record,
        adds a Boolean field to true
        indicates that the partner is a company
        """
        context = context or {}
        context.update({'create_company': True})
        return super(res_users, self).write(cr, uid, ids, values,
                                            context=context)

res_users()
