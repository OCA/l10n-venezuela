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

from odoo import models, fields


class AccountTax(models.Model):
    _inherit = 'account.tax'

    ret = fields.Boolean(
        string='Retención',
        help="indica si el impuesto puede ser retenido")
    wh_vat_collected_account_id = fields.Many2one(
        'account.account',
        string="Cuenta de Retención",
        help="esta cuenta sera usada para aplicar retenciones de impuesto")
    wh_vat_paid_account_id = fields.Many2one(
        'account.account',
        string="Cuenta de Retención para devoluciones",
        help="Esta cuenta sera utilizada para aplicar una retención a una devolución")
