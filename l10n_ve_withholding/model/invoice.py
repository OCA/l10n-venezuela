#!/usr/bin/python
# -*- encoding: utf-8 -*-
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

import time

from openerp.osv import fields, osv
from openerp.tools.translate import _


class account_invoice(osv.osv):
    _inherit = 'account.invoice'

    def test_retenida(self, cr, uid, ids, *args):
        """ Verify if this invoice is withhold
        """
        type2journal = {'out_invoice': 'iva_sale',
                        'in_invoice': 'iva_purchase', 'out_refund': 'iva_sale',
                        'in_refund': 'iva_purchase'}
        type_inv = self.browse(cr, uid, ids[0]).type
        type_journal = type2journal.get(type_inv, 'iva_purchase')
        res = self.ret_payment_get(cr, uid, ids)
        if not res:
            return False
        ok = True

        cr.execute('select l.id '
                   'from account_move_line l '
                   'inner join account_journal j on (j.id=l.journal_id)'
                   ' where l.id in (' + ','.join(
                       [str(item) for item in res]) + ') and j.type=' + '\''
                   + type_journal + '\'')
        ok = ok and bool(cr.fetchone())
        return ok

    def _get_move_lines(self, cr, uid, ids, to_wh, period_id,
                        pay_journal_id, writeoff_acc_id,
                        writeoff_period_id, writeoff_journal_id, date,
                        name, context=None):
        """ Function openerp is rewritten for adaptation in
        the ovl
        """
        if context is None:
            context = {}
        return []

    def ret_and_reconcile(self, cr, uid, ids, pay_amount, pay_account_id,
                          period_id, pay_journal_id, writeoff_acc_id,
                          writeoff_period_id, writeoff_journal_id, date,
                          name, to_wh, context=None):
        """ Make the payment of the invoice
        """
        if context is None:
            context = {}
        rp_obj = self.pool.get('res.partner')

        # TODO check if we can use different period for payment and the
        # writeoff line
        assert len(ids) == 1, "Can only pay one invoice at a time"
        invoice = self.browse(cr, uid, ids[0])
        src_account_id = invoice.account_id.id

        # Take the seq as name for move
        types = {'out_invoice': -1,
                 'in_invoice': 1,
                 'out_refund': 1, 'in_refund': -1}
        direction = types[invoice.type]
        l1 = {
            'debit': direction * pay_amount > 0 and direction * pay_amount,
            'credit': direction * pay_amount < 0 and - direction * pay_amount,
            'account_id': src_account_id,
            'partner_id': rp_obj._find_accounting_partner(
                invoice.partner_id).id,
            'ref': invoice.number,
            'date': date,
            'currency_id': False,
            'name': name
        }
        lines = [(0, 0, l1)]

        l2 = self._get_move_lines(
            cr, uid, ids, to_wh, period_id, pay_journal_id, writeoff_acc_id,
            writeoff_period_id, writeoff_journal_id, date,
            name, context=context)

        if not l2:
            raise osv.except_osv(
                _('Warning !'),
                _('No accounting moves were created.\n Please, Check if there'
                  ' are Taxes/Concepts to withhold in the Invoices!'))
        lines += l2

        move = {'ref': invoice.number, 'line_id': lines,
                'journal_id': pay_journal_id, 'period_id': period_id,
                'date': date}
        move_id = self.pool.get('account.move').create(cr, uid, move,
                                                       context=context)

        self.pool.get('account.move').post(cr, uid, [move_id])

        line_ids = []
        total = 0.0
        line = self.pool.get('account.move.line')
        cr.execute(
            'select id'
            ' from account_move_line'
            ' where move_id in (' + str(move_id) + ','
            + str(invoice.move_id.id) + ')')
        lines = line.browse(cr, uid, [item[0] for item in cr.fetchall()])
        for aml_brw in lines + invoice.payment_ids:
            if aml_brw.account_id.id == src_account_id:
                line_ids.append(aml_brw.id)
                total += (aml_brw.debit or 0.0) - (aml_brw.credit or 0.0)
        if (not round(total, self.pool.get('decimal.precision').precision_get(
                cr, uid, 'Withhold'))) or writeoff_acc_id:
            self.pool.get('account.move.line').reconcile(
                cr, uid, line_ids, 'manual', writeoff_acc_id,
                writeoff_period_id, writeoff_journal_id, context)
        else:
            self.pool.get('account.move.line').reconcile_partial(
                cr, uid, line_ids, 'manual', context)

        # Update the stored value (fields.function), so we write to trigger
        # recompute
        self.pool.get('account.invoice').write(cr, uid, ids, {},
                                               context=context)
        return {'move_id': move_id}

    def ret_payment_get(self, cr, uid, ids, *args):
        """ Return payments associated with this bill
        """
        # /!\ This method need revision and I (hbto) have come to believe it is
        # useless at worst, at best it needs to be refactored, to get payments
        # from invoice one just need to look at the payment_ids field

        lines = []
        for invoice in self.browse(cr, uid, ids):
            moves = self.move_line_id_payment_get(cr, uid, [invoice.id])
            src = []
            for aml_brw in self.pool.get('account.move.line').browse(cr, uid,
                                                                     moves):
                temp_lines = []  # Added temp list to avoid duplicate records
                if aml_brw.reconcile_id:
                    temp_lines = [i.id for i in aml_brw.reconcile_id.line_id]
                elif aml_brw.reconcile_partial_id:
                    temp_lines = [
                        i.id
                        for i in aml_brw.reconcile_partial_id.line_partial_ids]

                lines = list(set(temp_lines))
                src.append(aml_brw.id)

            lines += [item for item in lines if item not in src]
        return lines

    def check_tax_lines(self, cr, uid, inv, compute_taxes, ait_obj):
        """ Check if no tax lines are created. If
        existing tax lines, there are checks on the invoice
        and match the tax base.
        """
        if not inv.tax_line:
            for tax in compute_taxes.values():
                ait_obj.create(cr, uid, tax)
        else:
            tax_key = []
            for tax in inv.tax_line:
                if tax.manual:
                    continue
#                key = (tax.tax_code_id.id, tax.base_code_id.id,
#                       tax.account_id.id)
                # group by tax id #
                key = (tax.tax_id.id)
                tax_key.append(key)
                if key not in compute_taxes:
                    raise osv.except_osv(
                        _('Warning !'),
                        _('Global taxes defined, but are not in invoice'
                          ' lines !'))
                base = compute_taxes[key]['base']
                if abs(base - tax.base) > inv.company_id.currency_id.rounding:
                    raise osv.except_osv(
                        _('Warning !'),
                        _('Tax base different !\nClick on compute to update'
                          ' tax base'))
            for key in compute_taxes:
                if key not in tax_key:
                    raise osv.except_osv(_('Warning !'), _('Taxes missing !'))


class account_invoice_tax(osv.osv):
    _inherit = 'account.invoice.tax'
    _columns = {
        'tax_id': fields.many2one(
            'account.tax', 'Tax', required=False, ondelete='set null',
            help="Tax relation to original tax, to be able to take off all"
                 " data from invoices."),
    }

    def compute(self, cr, uid, invoice_id, context=None):
        """ Calculate the amount, base, tax amount,
        base amount of the invoice
        """

        tax_grouped = {}
        tax_obj = self.pool.get('account.tax')
        cur_obj = self.pool.get('res.currency')
        inv = self.pool.get('account.invoice').browse(
            cr, uid, invoice_id, context=context)
        cur = inv.currency_id
        company_currency = inv.company_id.currency_id.id

        for line in inv.invoice_line:
            for tax in tax_obj.compute_all(
                    cr, uid, line.invoice_line_tax_id,
                    (line.price_unit * (1 - (line.discount or 0.0) / 100.0)),
                    line.quantity, line.product_id, inv.partner_id)['taxes']:
                val = {}
                val['invoice_id'] = inv.id
                val['name'] = tax['name']
                val['amount'] = tax['amount']
                val['manual'] = False
                val['sequence'] = tax['sequence']
                val['base'] = tax['price_unit'] * line['quantity']
                # add tax id #
                val['tax_id'] = tax['id']

                if inv.type in ('out_invoice', 'in_invoice'):
                    val['base_code_id'] = tax['base_code_id']
                    val['tax_code_id'] = tax['tax_code_id']
                    val['base_amount'] = cur_obj.compute(
                        cr, uid, inv.currency_id.id, company_currency,
                        val['base'] * tax['base_sign'],
                        context={'date':
                                 inv.date_invoice or
                                 time.strftime('%Y-%m-%d')},
                        round=False)
                    val['tax_amount'] = cur_obj.compute(
                        cr, uid, inv.currency_id.id, company_currency,
                        val['amount'] * tax['tax_sign'],
                        context={'date':
                                 inv.date_invoice or
                                 time.strftime('%Y-%m-%d')},
                        round=False)
                    val['account_id'] = tax['account_collected_id'] or \
                        line.account_id.id
                else:
                    val['base_code_id'] = tax['ref_base_code_id']
                    val['tax_code_id'] = tax['ref_tax_code_id']
                    val['base_amount'] = cur_obj.compute(
                        cr, uid, inv.currency_id.id, company_currency,
                        val['base'] * tax['ref_base_sign'],
                        context={'date':
                                 inv.date_invoice or
                                 time.strftime('%Y-%m-%d')},
                        round=False)
                    val['tax_amount'] = cur_obj.compute(
                        cr, uid, inv.currency_id.id, company_currency,
                        val['amount'] * tax['ref_tax_sign'],
                        context={'date':
                                 inv.date_invoice
                                 or time.strftime('%Y-%m-%d')},
                        round=False)
                    val['account_id'] = tax['account_paid_id'] or \
                        line.account_id.id

#                key = (val['tax_code_id'], val['base_code_id'],
#                       val['account_id'])
                # group by tax id #
                key = (val['tax_id'])
                if key not in tax_grouped:
                    tax_grouped[key] = val
                else:
                    tax_grouped[key]['amount'] += val['amount']
                    tax_grouped[key]['base'] += val['base']
                    tax_grouped[key]['base_amount'] += val['base_amount']
                    tax_grouped[key]['tax_amount'] += val['tax_amount']

        for tax in tax_grouped.values():
            tax['base'] = cur_obj.round(cr, uid, cur, tax['base'])
            tax['amount'] = cur_obj.round(cr, uid, cur, tax['amount'])
            tax['base_amount'] = cur_obj.round(
                cr, uid, cur, tax['base_amount'])
            tax['tax_amount'] = cur_obj.round(cr, uid, cur, tax['tax_amount'])
        return tax_grouped
