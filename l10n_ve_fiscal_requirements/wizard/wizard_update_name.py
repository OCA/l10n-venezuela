# coding: utf-8
###########################################################################
#    Module Writen to OpenERP, Open Source Management Solution
#    Copyright (C) OpenERP Venezuela (<http://openerp.com.ve>).
#    All Rights Reserved
###############################################################################
#    Credits:
#    Coded by: Yanina Aular <yanina.aular@vauxoo.com>
#    Planified by: Humberto Arocha
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
from openerp.tools.translate import _


class WizUpdatename(osv.osv_memory):
    _name = 'wiz.updatename'
    _description = "Wizard that changes the partner name"

    def set_name(self, cr, uid, ids, context):
        """ Change value of the name field
        """
        data = self.pool.get('wiz.updatename').read(cr, uid, ids)[0]
        if not data['sure']:
            raise osv.except_osv(
                _("Error!"),
                _("Please confirm that you want to do this by checking the"
                  " option"))

        partner_obj = self.pool.get('res.partner')
        name_partner = data['name']

        partner_obj.write(cr, uid, context['active_id'],
                          {'name': name_partner}, context=context)
        return {}

    def _get_name(self, cr, uid, context=None):
        """ Get name field value
        """
        if context is None:
            context = {}
        partner_obj = self.pool.get('res.partner')
        partner = partner_obj.search(cr, uid,
                                     [('id', '=', context['active_id'])])
        partner_o = partner_obj.browse(cr, uid, partner[0])
        return partner_o and partner_o.name or False

    _columns = {
        'name': fields.char(
            string='Name', size=256, required=True,
            default=lambda s: s._get_name()),
        'sure': fields.boolean('Are you sure?'),
    }

WizUpdatename()
