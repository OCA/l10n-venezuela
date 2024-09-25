# -*- coding: utf-8 -*-
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

import os
import re

from odoo import api, fields, models, tools, _
from odoo.exceptions import ValidationError

class ResCompany(models.Model):
    _inherit = 'res.company'
    rif = fields.Char(string='RIF', required=True)
    purchase_iva_ret_account = fields.Many2one('account.account', string='Cuenta Ret. IVA proveedor')
    sale_iva_ret_account = fields.Many2one('account.account', string='Cuenta Ret. IVA cliente')
    purchase_islr_ret_account = fields.Many2one('account.account', string='Cuenta Ret. ISLR proveedor')
    sale_islr_ret_account = fields.Many2one('account.account', string='Cuenta Ret. ISLR cliente')