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
from datetime import timedelta
from odoo.addons import decimal_precision as dp
from odoo import models, fields, api, exceptions, _
from odoo.tools import float_compare, float_is_zero

TYPE2JOURNAL = {
    'out_invoice': 'sale',
    'in_invoice': 'purchase',
    'out_refund': 'sale',
    'in_refund': 'purchase',
}

class AccountWhIva(models.Model):
    _name = "account.wh.islr"
    _description = "Withholding ISLR"

    @api.multi
    def action_cancel_draft(self):
        moves = self.mapped('move_id')
        moves.filtered(lambda x: x.state == 'posted').button_cancel()
        moves.unlink()
        self.write({'state': 'draft'})

    @api.multi
    def action_draft(self):
        self.write({'state': 'draft'})

    @api.multi
    def action_confirm(self):
        type = reduce(lambda x, y: x if x == y else False, self.mapped('type'))
        self.write({'state': 'confirmed',
                    'number': self.env['ir.sequence'].next_by_code('account.wh.islr.%s'%type) if type =='in_invoice' else '',
                    })

    @api.multi
    def action_done(self):
        precision = self.env['decimal.precision'].precision_get('Withhold')
        for wh in self:
            line_ids = []
            debit_sum = 0.0
            credit_sum = 0.0
            date = fields.Date.today() or wh.date
            name = _('With Holding %s') %(wh.name)
            move_dict = {
                'narration': name,
                'ref': wh.number,
                'journal_id': wh.journal_id.id,
                'date': date,
            }

            amount = wh.ret_amount
            if float_is_zero(amount, precision_digits=precision):
                continue

            if wh.type == 'in_invoice':
                debit_account_id = wh.partner_id.property_account_payable_id.id
                credit_account_id = wh.account_id.id
            else:
                debit_account_id = wh.account_id.id
                credit_account_id = wh.partner_id.property_account_receivable_id.id

            if debit_account_id:
                debit_line = (0, 0, {
                    'name': wh.name,
                    'partner_id': wh.partner_id.id,
                    'account_id': debit_account_id,
                    'journal_id': wh.journal_id.id,
                    'date': date,
                    'debit': amount > 0.0 and amount or 0.0,
                    'credit': amount < 0.0 and -amount or 0.0,
                    'invoice_id': wh.invoice_id.id,
                    # 'analytic_account_id': ,
                })
                line_ids.append(debit_line)
                debit_sum += debit_line[2]['debit'] - debit_line[2]['credit']

            if credit_account_id:
                credit_line = (0, 0, {
                    'name': wh.name,
                    'partner_id': wh.partner_id.id,
                    'account_id': credit_account_id,
                    'journal_id': wh.journal_id.id,
                    'date': date,
                    'debit': amount < 0.0 and -amount or 0.0,
                    'credit': amount > 0.0 and amount or 0.0,
                    'invoice_id': wh.invoice_id.id
                    # 'analytic_account_id': ,
                })
                line_ids.append(credit_line)
                credit_sum += credit_line[2]['credit'] - credit_line[2]['debit']

            if float_compare(credit_sum, debit_sum, precision_digits=precision) == -1:
                acc_id = wh.journal_id.default_credit_account_id.id
                if not acc_id:
                    raise UserError(
                        _('The Expense Journal "%s" has not properly configured the Credit Account!') % (
                        wh.journal_id.name))
                adjust_credit = (0, 0, {
                    'name': _('Adjustment Entry'),
                    'partner_id': False,
                    'account_id': acc_id,
                    'journal_id': wh.journal_id.id,
                    'date': date,
                    'debit': 0.0,
                    'credit': debit_sum - credit_sum,
                })
                line_ids.append(adjust_credit)

            elif float_compare(debit_sum, credit_sum, precision_digits=precision) == -1:
                acc_id = wh.journal_id.default_debit_account_id.id
                if not acc_id:
                    raise UserError(_('The Expense Journal "%s" has not properly configured the Debit Account!') % (
                    wh.journal_id.name))
                adjust_debit = (0, 0, {
                    'name': _('Adjustment Entry'),
                    'partner_id': False,
                    'account_id': acc_id,
                    'journal_id': wh.journal_id.id,
                    'date': date,
                    'debit': credit_sum - debit_sum,
                    'credit': 0.0,
                })
                line_ids.append(adjust_debit)
            move_dict['line_ids'] = line_ids
            move = self.env['account.move'].create(move_dict)
            wh.write({'move_id': move.id,
                      'date': date,
                      'state': 'done'})
            move.post()

    @api.model
    def _default_journal(self):
        if self._context.get('default_journal_id', False):
            return self.env['account.journal'].browse(self._context.get('default_journal_id'))
        inv_type = self._context.get('type', 'out_invoice')
        inv_types = inv_type if isinstance(inv_type, list) else [inv_type]
        company_id = self._context.get('company_id', self.env.user.company_id.id)
        domain = [
            ('type', 'in', filter(None, map(TYPE2JOURNAL.get, inv_types))),
            ('company_id', '=', company_id),
        ]
        return self.env['account.journal'].search(domain, limit=1)

    @api.onchange('partner_id')
    @api.model
    def _get_default_witholding_account(self):
    #    for record in self:
        if self.type == 'out_invoice':
            self.account_id = self.company_id.sale_islr_ret_account.id
        else:
            self.account_id = self.company_id.purchase_islr_ret_account.id

    move_id = fields.Many2one('account.move', 'Accounting Entry', readonly=True, copy=False)
    journal_id = fields.Many2one('account.journal', string='Journal',
        required=True, readonly=True, states={'draft': [('readonly', False)]},
        default=_default_journal,
        domain="[('type', 'in', {'out_invoice': ['sale'], 'out_refund': ['sale'], 'in_refund': ['purchase'], 'in_invoice': ['purchase']}.get(type, [])), ('company_id', '=', company_id)]")
    name = fields.Char(
        string='Descripción', size=64, readonly=True,
        states={'draft': [('readonly', False)]}, required=True,
        help="Descripción de la retención")
    number = fields.Char(
        string='Número de Comprobante', size=32, readonly=True,
        states={'draft': [('readonly', False)]},
        help="Número de comprobante")
    customer_doc_number = fields.Char(
        string='Nro Comprobante Cliente', size=32, readonly=True,
        states={'draft': [('readonly', False)]},
        help="Número de comprobante del cliente")
    type = fields.Selection([
        ('out_invoice', 'Customer Invoice'),
        ('in_invoice', 'Supplier Invoice'),
        ], string='Tipo', readonly=True,
        help="Tipo de retención")
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('confirmed', 'Confirmada'),
        ('done', 'hecho'),
        ('cancel', 'Cancelada')
        ], string='estatus', readonly=True, default='draft',
        help="estatus de la retención")
    date = fields.Date(
        string='Fecha', readonly=True,
        states={'draft': [('readonly', False)]},
        help="Fecha de la emisión del documento de retención")
    account_id = fields.Many2one(
        'account.account', compute='_get_default_witholding_account', string='Cuenta', required=True, readonly=True,
        states={'draft': [('readonly', False)]},
        help="Cuenta contable de la retención.")
    currency_id = fields.Many2one(
        'res.currency', string='Moneda', required=True, readonly=True,
        states={'draft': [('readonly', False)]}, help="Moneda",
        default=lambda self: self.env.user.company_id.currency_id.id)
    company_id = fields.Many2one(
        'res.company', string='Compañia', required=True, readonly=True,
        default=lambda self: self.env.user.company_id.id,
        help="Company")
    partner_id = fields.Many2one(
        'res.partner', string='Razón Social', readonly=True, required=True,
        states={'draft': [('readonly', False)]},
        help="Cliente o proveedor a retener")
    invoice_id = fields.Many2one('account.invoice', string='Factura', required=True,
        ondelete='restrict', help="Factura a retener")
    amount_invoice = fields.Monetary(string='Monto Factura',
                                     related='invoice_id.amount_untaxed',
                                     readonly=True,
                                     help="Factura a retener",
                                     store=True)
    porc_islr = fields.Float(string='% impuesto retenido', digits=dp.get_precision('Withhold'), required=True,
        help="Porcentaje de impuesto retenido" )
    ret_amount = fields.Float(string='ISLR Retenido', digits=dp.get_precision('Withhold'),
        help="Monto a retener", required=True)
    
    _sql_constraints = [
        ('ret_fact_uniq', 'unique (invoice_id)', 'La factura ya ha sido asginada a un'
         ' comprobante de retención, no la puedas asignar dos veces')
    ]
