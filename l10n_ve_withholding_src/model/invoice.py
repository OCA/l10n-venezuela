#!/usr/bin/python
# -*- encoding: utf-8 -*-
###########################################################################
#    Module Writen to OpenERP, Open Source Management Solution
#    Copyright (C) OpenERP Venezuela (<http://openerp.com.ve>).
#    All Rights Reserved
###############################################################################
#    Credits:
#    Coded by: Humberto Arocha <hbto@vauxoo.com>
#    Planified by: Humberto Arocha / Nhomar Hernandez
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

from openerp.addons import decimal_precision as dp
from openerp.osv import fields, osv
from openerp.tools.translate import _


class account_invoice(osv.osv):
    _inherit = 'account.invoice'

    def onchange_partner_id(self, cr, uid, ids, inv_type, partner_id,
                            date_invoice=False, payment_term=False,
                            partner_bank_id=False, company_id=False):
        """ Change invoice information depending of the partner
        @param type: Invoice type
        @param partner_id: Partner id of the invoice
        @param date_invoice: Date invoice
        @param payment_term: Payment terms
        @param partner_bank_id: Partner bank id of the invoice
        @param company_id: Company id
        """
        rp_obj = self.pool.get('res.partner')
        res = super(account_invoice, self).onchange_partner_id(
            cr, uid, ids, inv_type, partner_id, date_invoice, payment_term,
            partner_bank_id, company_id)

        if inv_type in ('out_invoice',):
            rp_brw = rp_obj._find_accounting_partner(
                rp_obj.browse(cr, uid, partner_id))
            res['value']['wh_src_rate'] = rp_brw.wh_src_agent and \
                rp_brw.wh_src_rate or 0
        else:
            ru_brw = self.pool.get('res.users').browse(cr, uid, uid)
            rp_brw = rp_obj._find_accounting_partner(
                ru_brw.company_id.partner_id)
            res['value']['wh_src_rate'] = rp_brw.wh_src_agent and \
                rp_brw.wh_src_rate or 0
        return res

    def _check_retention(self, cr, uid, ids, context=None):
        """ This method will check the retention value will be maximum 5%
        """
        if context is None:
            context = {}

        invoice_brw = self.browse(cr, uid, ids)

        ret = invoice_brw[0].wh_src_rate

        if ret and ret > 5:
            return False

        return True

    _columns = {
        'wh_src': fields.boolean(
            'Social Responsibility Commitment Withheld',
            help='if the commitment to social responsibility has been'
                 ' retained'),
        'wh_src_rate': fields.float(
            'SRC Wh rate', digits_compute=dp.get_precision('Withhold'),
            readonly=True, states={'draft': [('readonly', False)]},
            help="Social Responsibility Commitment Withholding Rate"),
        'wh_src_id': fields.many2one(
            'account.wh.src', 'Wh. SRC Doc.', readonly=True,
            help="Social Responsibility Commitment Withholding Document"),
    }
    _defaults = {
        'wh_src': False,
    }

    _constraints = [
        (_check_retention, _("Error ! Maximum retention is 5%"), []),
    ]

    def _get_move_lines(self, cr, uid, ids, to_wh, period_id,
                        pay_journal_id, writeoff_acc_id,
                        writeoff_period_id, writeoff_journal_id, date,
                        name, context=None):
        """ Generate move lines in corresponding account
        @param to_wh: whether or not withheld
        @param period_id: Period
        @param pay_journal_id: pay journal of the invoice
        @param writeoff_acc_id: account where canceled
        @param writeoff_period_id: period where canceled
        @param writeoff_journal_id: journal where canceled
        @param date: current date
        @param name: description
        """
        context = context or {}
        res = super(account_invoice, self)._get_move_lines(
            cr, uid, ids, to_wh, period_id, pay_journal_id, writeoff_acc_id,
            writeoff_period_id, writeoff_journal_id, date, name,
            context=context)
        rp_obj = self.pool.get('res.partner')
        if context.get('wh_src', False):
            invoice = self.browse(cr, uid, ids[0])
            acc_part_brw = rp_obj._find_accounting_partner(invoice.partner_id)
            types = {
                'out_invoice': -1,
                'in_invoice': 1,
                'out_refund': 1, 'in_refund': -1}
            direction = types[invoice.type]

            for tax_brw in to_wh:
                if types[invoice.type] == 1:
                    acc = (
                        tax_brw.wh_id.company_id.wh_src_collected_account_id
                        and
                        tax_brw.wh_id.company_id.wh_src_collected_account_id.id
                        or False)
                else:
                    acc = (tax_brw.wh_id.company_id.wh_src_paid_account_id and
                           tax_brw.wh_id.company_id.wh_src_paid_account_id.id
                           or False)
                if not acc:
                    raise osv.except_osv(
                        _('Missing Account in Company!'),
                        _("Your Company [%s] has missing account. Please, fill"
                          " the missing fields") % (
                              tax_brw.wh_id.company_id.name,))
                res.append((0, 0, {
                    'debit':
                    direction * tax_brw.wh_amount < 0 and
                    - direction * tax_brw.wh_amount,
                    'credit':
                    direction * tax_brw.wh_amount > 0 and
                    direction * tax_brw.wh_amount,
                    'account_id': acc,
                    'partner_id': acc_part_brw.id,
                    'ref': invoice.number,
                    'date': date,
                    'currency_id': False,
                    'name': name
                }))
        return res

    def action_cancel(self, cr, uid, ids, context=None):
        """ Verify first if the invoice have a non cancel src withholding doc.
        If it has then raise a error message. """
        context = context or {}
        for inv_brw in self.browse(cr, uid, ids, context=context):
            if not inv_brw.wh_src_id:
                super(account_invoice, self).action_cancel(cr, uid, ids,
                                                           context=context)
            else:
                raise osv.except_osv(
                    _("Error!"),
                    _("You can't cancel an invoice that have non cancel"
                      " Src Withholding Document. Needs first cancel the"
                      " invoice Src Withholding Document and then you can"
                      " cancel this invoice."))
        return True
