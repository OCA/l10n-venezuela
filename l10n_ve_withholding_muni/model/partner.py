#!/usr/bin/python
# -*- encoding: utf-8 -*-
###########################################################################
#    Module Writen to OpenERP, Open Source Management Solution
#    Copyright (C) OpenERP Venezuela (<http://openerp.com.ve>).
#    All Rights Reserved
# Credits######################################################
#    Coded by: Javier Duran <jduran@corvus.com.ve>
#    Planified by: Nhomar Hernandez
#    Audited by: Vauxoo C.A.
#############################################################################
#    Copyright (c) 2009 Latinux Inc (http://www.latinux.com/) All Rights
#    Reserved.  This program is free software: you can redistribute it and/or
#    modify it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
##########################################################################

from openerp.osv import fields, osv


class res_partner(osv.osv):
    _inherit = 'res.partner'
    _columns = {
        'property_wh_munici_payable': fields.property(
            'account.account',
            type='many2one',
            relation='account.account',
            string="Purchase local withholding account",
            method=True,
            view_load=True,
            domain="[('type', '=', 'other')]",
            help="This account will be used debit local withholding amount"),
        'property_wh_munici_receivable': fields.property(
            'account.account',
            type='many2one',
            relation='account.account',
            string="Sale local withholding account",
            method=True,
            view_load=True,
            domain="[('type', '=', 'other')]",
            help="This account will be used credit local withholding amount"),

    }
